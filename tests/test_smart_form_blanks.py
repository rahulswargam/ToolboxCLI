from pathlib import Path
import io
import fitz
import pytest
from PySide6.QtCore import Qt,QPointF
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QInputDialog
from toolboxdesktop.pdf_forms import detect_fields,native_fields,save_filled_pdf
from toolboxdesktop.pdf_workspace import PdfWorkspace
from toolboxdesktop.catalog import TOOLS
from toolboxdesktop.field_editors import CombLineEdit
from test_desktop_ui import window


def settle():
    for _ in range(4):QApplication.instance().processEvents()


@pytest.fixture
def boxed_form(tmp_path):
    path=tmp_path/'character-box-form.pdf'
    with fitz.open() as doc:
        page=doc.new_page(width=600,height=800)
        page.draw_rect(fitz.Rect(30,25,570,65),color=None,fill=(.1,.3,.5))
        page.insert_text((45,50),'APPLICATION FORM',fontsize=18,color=(1,1,1))
        for label,y,count,gap in [('Full name:',110,18,2),('Account number:',160,12,2),('Date of birth:',210,8,0),('Email:',260,20,1)]:
            page.insert_text((35,y+11),label,fontsize=10)
            for i in range(count):
                r=fitz.Rect(160+i*(15+gap),y,175+i*(15+gap),y+16)
                page.draw_rect(r,color=(.55,.55,.55),width=.6)
                if 'birth' in label:page.insert_text((r.x0+4,r.y1-4),'DDMMYYYY'[i],fontsize=8,color=(.75,.75,.75))
        page.draw_rect(fitz.Rect(45,310,59,324),color=(.4,.4,.4))
        page.insert_text((68,321),'I agree',fontsize=10)
        page.draw_rect(fitz.Rect(45,350,320,385),color=(.4,.4,.4))
        page.insert_text((45,341),'Address:',fontsize=10)
        page.draw_rect(fitz.Rect(45,430,300,480),color=(.4,.4,.4))
        page.insert_text((45,500),'Applicant Signature',fontsize=10)
        page.draw_rect(fitz.Rect(440,320,550,455),color=(.4,.4,.4))
        page.insert_text((453,385),'Photograph',fontsize=10)
        doc.new_page(width=600,height=800)
        doc[1].draw_rect(fitz.Rect(100,100,450,130))
        doc[1].insert_text((100,90),'City:')
        doc.save(path)
    return path


def test_character_cells_group_into_fields_not_checkboxes(boxed_form):
    fields,_=detect_fields(boxed_form,0)
    comb=[f for f in fields if f['kind']=='comb']
    assert sorted(f['max_length'] for f in comb)==[8,12,18,20]
    assert len([f for f in fields if f['kind']=='checkbox'])==1
    assert not any('Photograph' in f['label'] for f in fields)
    date=next(f for f in comb if 'birth' in f['label'])
    assert date['input_type']=='digits'
    assert len({f['id'] for f in fields})==len(fields)
    again,_=detect_fields(boxed_form,0)
    assert [f['id'] for f in fields]==[f['id'] for f in again]


def test_click_type_tab_and_paste_stay_in_detected_blanks(window,boxed_form,monkeypatch):
    editor=PdfWorkspace(window,next(t for t in TOOLS if t.key=='fill_pdf'),files=[str(boxed_form)])
    editor.showMaximized();settle()
    assert editor.mode=='fill'
    monkeypatch.setattr(QInputDialog,'getMultiLineText',lambda *a,**k:pytest.fail('Detected fields must type inline, without a popup'))
    fields=editor.fields_by_page[0]
    name=next(f for f in fields if f['kind']=='comb' and 'name' in f['label'].lower())
    account=next(f for f in fields if 'Account' in f['label'])
    dob=next(f for f in fields if 'birth' in f['label'])
    widget=editor.field_proxies[name['id']].widget()
    assert isinstance(widget,CombLineEdit)
    editor.activate_field(name)
    QTest.keyClicks(widget,'ALEX MORGAN');settle()
    assert editor.values[name['id']]=='ALEX MORGAN'
    assert not editor.annotations
    QTest.keyClick(widget,Qt.Key.Key_Tab);settle()
    target=editor.field_proxies[account['id']].widget()
    assert target.hasFocus()
    QTest.keyClicks(target,'001234567890');settle()
    assert target.text()=='001234567890'
    QTest.keyClicks(target,'123')
    assert target.text()=='001234567890'
    editor.activate_field(dob)
    target=editor.field_proxies[dob['id']].widget()
    QApplication.clipboard().setText('21/11/2026')
    QTest.keyClick(target,Qt.Key.Key_V,Qt.KeyboardModifier.ControlModifier)
    assert target.text()=='21112026'
    check=next(f for f in fields if f['kind']=='checkbox')
    checkbox=editor.field_proxies[check['id']].widget()
    QTest.mouseClick(checkbox,Qt.MouseButton.LeftButton)
    assert editor.values[check['id']] is True
    # Clicking a printed heading cannot create a free-floating text/check entry.
    point=editor.view.mapFromScene(QPointF(100,50))
    QTest.mouseClick(editor.view.viewport(),Qt.MouseButton.LeftButton,pos=point)
    assert not editor.annotations
    editor.dirty=False;editor.reject()


def test_export_creates_real_comb_fields_and_keeps_characters_inside_cells(boxed_form,tmp_path):
    fields,_=detect_fields(boxed_form,0)
    name=next(f for f in fields if f['kind']=='comb' and 'name' in f['label'].lower())
    account=next(f for f in fields if 'Account' in f['label'])
    dob=next(f for f in fields if 'birth' in f['label'])
    values={name['id']:'ALEX MORGAN',account['id']:'001234567890',dob['id']:'21112026'}
    out=tmp_path/'real-fillable.pdf'
    save_filled_pdf(boxed_form,out,values,[],detected_fields=fields)
    with fitz.open(out) as doc:
        native=native_fields(doc[0])
        name_field=next(f for f in native if f['label']==name['label'])
        assert name_field['kind']=='comb' and name_field['max_length']==18
        assert name_field['value']=='ALEX MORGAN'
        assert next(f for f in native if f['label']==account['label'])['value']=='001234567890'
        characters=[char for block in doc[0].get_text('rawdict')['blocks'] if 'lines' in block for line in block['lines'] for span in line['spans'] if 'Cour' in span['font'] for char in span['chars']]
        number_chars=[c for c in characters if 159<c['bbox'][1]<177]
        assert ''.join(c['c'] for c in number_chars)=='001234567890'
        for char,cell in zip(number_chars,account['cell_rects']):
            center=fitz.Rect(char['bbox']).tl+fitz.Point((char['bbox'][2]-char['bbox'][0])/2,(char['bbox'][3]-char['bbox'][1])/2)
            assert fitz.Rect(cell).contains(center)
    flattened=tmp_path/'flat-filled.pdf'
    save_filled_pdf(boxed_form,flattened,values,[],True,fields)
    with fitz.open(flattened) as doc:
        assert not list(doc[0].widgets() or [])


def test_connected_character_grid_in_scan_is_grouped(boxed_form,tmp_path):
    scan=tmp_path/'scanned.pdf'
    with fitz.open(boxed_form) as source,fitz.open() as output:
        pix=source[0].get_pixmap(matrix=fitz.Matrix(2,2))
        page=output.new_page(width=600,height=800)
        page.insert_image(page.rect,stream=pix.tobytes('png'))
        output.save(scan)
    fields,_=detect_fields(scan,0,False)
    counts=[f['max_length'] for f in fields if f['kind']=='comb']
    assert 8 in counts and 18 in counts and 12 in counts


def test_actual_hdfc_form_box_counts_and_export(tmp_path):
    source=Path(__file__).resolve().parent.parent/'artifacts/form-research/hdfc-minor-to-major.pdf'
    if not source.exists():pytest.skip('Download the public HDFC QA document; see docs/form-filling-research.md')
    fields,_=detect_fields(source,0)
    comb=[f for f in fields if f['kind']=='comb']
    expected=[('Customer ID',9),('Bank A/c',14),('Date:*',8),('PAN Number',10),('AADHAAR',12),('Mobile',10),('Email',31)]
    for label,count in expected:
        assert any(label in f['label'] and f['max_length']==count for f in comb),(label,count)
    assert any('Mothers' in f['label'] and f['max_length']==31 for f in comb)
    assert any('Nationality' in f['label'] and f['max_length']==19 for f in comb)
    assert all(not any(fitz.Rect(cell).intersects(fitz.Rect(check['rect'])) for check in fields if check['kind']=='checkbox') for group in comb for cell in group['cell_rects'])
    customer=next(f for f in comb if 'Customer ID' in f['label'])
    out=tmp_path/'hdfc-test-filled.pdf'
    save_filled_pdf(source,out,{customer['id']:'123456789'},[],detected_fields=fields)
    with fitz.open(out) as doc:
        assert any(w.field_value=='123456789' for w in doc[0].widgets())
