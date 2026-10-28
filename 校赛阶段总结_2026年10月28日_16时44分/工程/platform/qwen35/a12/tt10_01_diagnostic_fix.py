"""Independent source-04; changes only raw diagnostic file I/O, not model math."""
import difflib,shutil
from tt10_01_common import ROOT,OUT,sha,save


def main():
    before=OUT/'source-03';after=OUT/'source-04';shutil.copytree(before,after)
    shutil.copyfile(ROOT/'runtime/qwen35_w4a8/a12/tt10_01/diagnostic_io.hpp',after/'diagnostic_io.hpp')
    replacements={
        'main.cpp':('static void write_binary(const std::filesystem::path&p,const void*v,size_t bytes){if(std::filesystem::exists(p))throw std::runtime_error("diagnostic path already exists");std::ofstream f(p,std::ios::binary);f.write(static_cast<const char*>(v),bytes);if(!f)throw std::runtime_error("diagnostic write");}',
                    'static void write_binary(const std::filesystem::path&p,const void*v,size_t bytes){tt10::write_diagnostic(p,v,bytes);}'),
        'bridge.cpp':('std::ofstream f(p,std::ios::binary);f.write(reinterpret_cast<const char*>(v.data()),v.size()*4);if(!f)throw std::runtime_error("dump failed");',
                      'tt10::write_diagnostic(p,v.data(),v.size()*4);')}
    patches=[]
    for name,(old,new) in replacements.items():
        p=after/name;original=p.read_text(encoding='utf-8');assert original.count(old)==1
        changed='#include "diagnostic_io.hpp"\n'+original.replace(old,new)
        # Invert the exact diagnostic-only edits to prove every other byte unchanged.
        assert changed.split('\n',1)[1].replace(new,old)==original
        p.write_text(changed,encoding='utf-8',newline='\n')
        patches.extend(difflib.unified_diff(original.splitlines(True),changed.splitlines(True),fromfile='source-03/'+name,tofile='source-04/'+name))
    (OUT/'diagnostic-resource-04.patch').write_text(''.join(patches),encoding='utf-8')
    save(OUT/'DERIVATION-04.json',dict(status='DIAGNOSTIC_IO_ONLY_CANDIDATE_NOT_BOARD_TESTED',base='source-03',
        changed=['main.cpp diagnostic writer','bridge.cpp diagnostic writer'],added=['diagnostic_io.hpp'],
        computation_and_state_logic_byte_unchanged_after_inverting_IO_edits=True,
        preserves='No changes to permits/fsync journal/math/PL/01A/03; only completed owned diagnostic file pages receive DONTNEED after fsync',
        sources={p.name:sha(p) for p in after.iterdir() if p.is_file()},BOARD='NOT_TESTED'))
    print('SOURCE04_DIAGNOSTIC_IO_ONLY_DERIVED')


if __name__=='__main__':main()
