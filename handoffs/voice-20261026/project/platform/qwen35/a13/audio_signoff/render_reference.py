"""Download the public datasheet and render timing tables, no local image edits."""
from pathlib import Path
import hashlib
import json
import urllib.request
import pypdfium2 as pdfium

OUT = Path(__file__).resolve().parents[4] / 'evidence/a13_A/20261024-audio-offline-signoff-v1/references'
URL = 'https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/307/WM8960.pdf'


def main():
    OUT.mkdir(exist_ok=False)
    with urllib.request.urlopen(URL, timeout=30) as response:
        data = response.read()
    assert data.startswith(b'%PDF-')
    with (OUT / 'WM8960.pdf').open('xb') as stream:
        stream.write(data)
    document = pdfium.PdfDocument(OUT / 'WM8960.pdf')
    assert len(document) == 94
    for index in [14, 15, 58, 59, 62]:
        page = document[index]
        page.render(scale=1.5).to_pil().save(OUT / f'WM8960-printed-page-{index+1}.png')
    with (OUT / 'SOURCE.json').open('x', encoding='utf-8') as stream:
        json.dump({'url': URL, 'sha256': hashlib.sha256(data).hexdigest(),
                   'pages': len(document), 'rendered_zero_based_pages': [14, 15, 58, 59, 62]}, stream, indent=2)
    print('WM8960 manufacturer timing/clock pages rendered; no board access')


if __name__ == '__main__':
    main()
