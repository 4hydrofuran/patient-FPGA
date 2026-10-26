"""Real Linux child/permits/locks; fake hardware only, never BOARD evidence."""
from pathlib import Path
text=Path(__file__).with_name('test_management.py').read_text()
text=text.replace("ops += [('submit',row['job_id']),('completed',row['job_id'])]",
                  "if row['job_id']==1:ops.append(('invalid_parameters',1))\n    ops += [('submit',row['job_id']),('completed',row['job_id'])]")
text=text.replace("(source/'permits').mkdir()", """if mode=='closed_failure':
    ops=ops[:4]+[('abort_close',1)]
(source/'permits').mkdir()""")
text=text.replace("for row in plan['schedule']:\n    rows.append", "for row in (plan['schedule'][:1] if mode=='closed_failure' else plan['schedule']):\n    rows.append")
text=text.replace('numeric_pass=True,guards_intact=True','numeric_pass=True,quant_bytes_match=True,guards_intact=True')
text=text.replace("if mode=='worker_identity':", """if mode=='closed_failure':
    r.update(status='FAILED_CLOSED_A11_MINIMAL',real_submissions=1,weight_loads=1,
             failure_kind='COMPLETED_NUMERIC_OR_QUANT_MISMATCH',failed_job=1,failure_code=None,
             context_disposition='CLOSED_AFTER_VALIDATED_COMPLETION')
    r['calls'][0]['numeric_pass']=False
if mode=='worker_identity':""")
text=text.replace("names={'mlp_worker.py'", "names={'compute_result.py','mlp_worker.py'")
text=text.replace('self.obj.permit_index,53','self.obj.permit_index,54')
text=text.replace("if __name__=='__main__':unittest.main(argv=[sys.argv[0],*remaining],verbosity=2)",'')
exec(compile(text,str(Path(__file__).with_name('test_management.py')),'exec'),globals())

class ComputeRecovery(Integration):
    def test_prepl_race_is_preserved_before_two_complete_reads(self):
        self.fault='prepl_race'
        self.assertEqual(self.execute(),0)
        events=self.events();names=[r['event'] for r in events]
        observations=[r for r in events if r['event']=='PROCESS_RELEASE_OBSERVATION']
        self.assertFalse(observations[0]['scan']['scan_complete'])
        self.assertTrue(any(r['scan']['scan_complete'] for r in observations[1:]))
        mutation=next(i for i,r in enumerate(events) if r['event']=='COMMAND_BEGIN' and r['state_changing'])
        self.assertLess(names.index('PREPL_TWO_COMPLETE_QUIET_READS'),mutation)
    def test_completed_numeric_failure_restores_without_claiming_success(self):
        self.fault='closed_failure'
        self.assertEqual(self.execute(),0)
        receipt=json.loads((self.source/'mlp-receipt.json').read_text())
        self.assertEqual(receipt['compute_runs'],1)
        self.assertEqual(receipt['status'],'FAILED_COMPUTE_NORMAL_RELEASE_REQUIRES_INDEPENDENT_AUDIT')
        self.assertEqual(self.events()[-1]['event'],'FAILED_MLP_DEFAULT_PL_RESTORED')
        self.assertEqual((self.gdm,self.overlay,self.module),('active',policy.DEFAULT,False))
        self.assertFalse((self.central/'active').exists());self.assertEqual(self.obj.held_locks,[])
        names=[r['event'] for r in self.events()]
        self.assertLess(names.index('WORKER_REAPED'),names.index('RELEASE_PRECHECK_PASSED_NOT_UNLOADED'))

del Integration  # Run the inherited suite once through ComputeRecovery.
if __name__=='__main__':unittest.main(argv=[sys.argv[0],*remaining],verbosity=2)
