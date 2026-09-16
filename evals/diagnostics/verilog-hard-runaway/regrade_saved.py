"""Regrade saved answers only. Never contacts a model or modifies originals."""
import json
import pathlib
import sys
import time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
import work_quality_suite as w
import deep_reasoning_suite as dr
import numpy as np
from eval_runtime import atomic_write_json

ROOT = pathlib.Path('/home/david/work/llmctl/evals/results/dw-spark0')
DEST = ROOT / 'same-grader-regrade-20260916'
DEST.mkdir(exist_ok=True)
factory_names = ['task_structured_protocol', 'task_bom', 'task_code_repair', 'task_code_review', 'task_protocol_design', 'task_long_context', 'task_scope_control', 'task_timing', 'task_cpp_easy', 'task_verilog_easy', 'task_cuda_easy', 'task_ml_easy', 'task_cobs_codec', 'task_stream_reassembler', 'task_verilog_medium', 'task_cuda_medium', 'task_cpp_medium', 'task_ml_medium', 'task_cpp_hard', 'task_verilog_hard', 'task_cuda_hard', 'task_ml_hard']
work = {t[0]: t[3] for t in [getattr(w, name)() for name in factory_names]}
reasoning = {t[0]: t[3] for t in dr.tasks(True)}
inputs = [('nvfp4-work', ROOT/'full-glm53-flash-nvfp4.json', work), ('exl3-work', ROOT/'glm53-fair-headless-low-20260916T194745Z/work_quality_suite.json', work), ('nvfp4-reasoning', ROOT/'full-deep-reasoning-glm53-flash-nvfp4.json', reasoning), ('exl3-reasoning', ROOT/'glm53-fair-headless-low-20260916T194745Z/deep_reasoning_suite.json', reasoning)]
for label, source, graders in inputs:
    original = json.loads(source.read_text())
    result = {'source':str(source), 'model':original['model'], 'numpy_version':np.__version__, 'original_score':original['score'], 'max_score':original['max_score'], 'status':'partial', 'tasks':[]}
    for row in original['tasks']:
        print(label, row['task'], flush=True)
        grader = graders[row['task']]
        score, maximum, details = grader(row['response'])
        new = {'task':row['task'], 'old_score':row['score'], 'score_first':score, 'max_score':maximum, 'first_details':details}
        credited = score
        if 'retry_response' in row:
            retry, _, retry_details = grader(row['retry_response'])
            new.update(score_retry=retry, retry_details=retry_details)
            credited = max(score, int(round(retry * original.get('retry_credit', 0.7))))
        new['score'] = credited
        result['tasks'].append(new)
        result['score'] = sum(t['score'] for t in result['tasks'])
        atomic_write_json(DEST/(label+'.json'), w._json_safe(result))
        print(json.dumps(w._json_safe(new)), flush=True)
    result['status']='complete'
    atomic_write_json(DEST/(label+'.json'), w._json_safe(result))
    print('TOTAL', label, result['score'], '/', result['max_score'], flush=True)
