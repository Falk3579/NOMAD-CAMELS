import json
import importlib.util
from pathlib import Path

src=Path(__file__).with_name('summarize_startup_timings.py')
spec=importlib.util.spec_from_file_location('summarize_startup_timings',src)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_summarizes_nested_and_repeated_phases(tmp_path):
    doc={'format_version':1,'events':[
      {'type':'mark','name':'launcher.start','start_ms':1},
      {'type':'mark','name':'launcher.show_called','start_ms':13001},
      {'type':'phase','name':'mainwindow.setup_ui','duration_ms':300,'start_ms':100},
      {'type':'phase','name':'mainwindow.setup_ui','duration_ms':50,'start_ms':200},
      {'type':'phase','name':'launcher.main_window_init','duration_ms':9000,'start_ms':10},
    ]}
    (tmp_path/'startup-20261111-120000-pid100.json').write_text(json.dumps(doc))
    result=module.summarize(tmp_path)
    assert '13000.0 ms' in result
    assert 'mainwindow.setup_ui' in result
    assert '350.0' in result
    assert '9000.0' in result


def test_empty_and_malformed_profiles(tmp_path):
    (tmp_path/'startup-bad.json').write_text('{broken')
    result=module.summarize(tmp_path)
    assert 'No valid startup timing files' in result
