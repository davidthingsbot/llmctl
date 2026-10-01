"""Fail-closed memory guard scoped only to the TensorFold trial container."""
import argparse,json,pathlib,subprocess,time

def unsafe(available_kib, floor_gib):
    return available_kib is None or available_kib < floor_gib*1048576

def main():
    p=argparse.ArgumentParser();p.add_argument('--container',default='glm53-flash-tf-trial');p.add_argument('--floor-gib',type=float,default=5);p.add_argument('--self-test',action='store_true');a=p.parse_args()
    if a.self_test:
        assert unsafe(None,5) and unsafe(4*1048576,5) and not unsafe(6*1048576,5)
        print('Memory guard threshold/missing-sample tests passed');return
    while True:
        try: available=int(next(l.split()[1] for l in pathlib.Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemAvailable:')))
        except Exception: available=None
        if unsafe(available,a.floor_gib):
            print(json.dumps({'event':'memory_guard_trip','available_kib':available,'floor_gib':a.floor_gib,'container':a.container}),flush=True)
            subprocess.run(['docker','kill',a.container],timeout=20,check=False)
            raise SystemExit(1)
        time.sleep(2)
if __name__=='__main__':main()
