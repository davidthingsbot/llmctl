"""Fail-closed memory guard scoped only to the TensorFold trial container."""
import argparse,json,pathlib,subprocess,time

def unsafe(available_kib, floor_gib):
    return available_kib is None or available_kib < floor_gib*1048576

def target_terminated(container):
    """Only a stopped state or a successful inventory proving absence is final."""
    result=subprocess.run(['docker','inspect','--format','{{json .State.Running}}',container],capture_output=True,text=True,timeout=20,check=False)
    if result.returncode==0:
        return result.stdout.strip()=='false'
    # An inspect error can mean either missing target or unavailable daemon.
    # Never interpret stderr (or an unsuccessful inventory) as proof of absence.
    result=subprocess.run(['docker','container','ls','--all','--no-trunc','--format','{{json .}}'],capture_output=True,text=True,timeout=20,check=False)
    if result.returncode!=0:
        return False
    for line in result.stdout.splitlines():
        row=json.loads(line)
        if container in row['Names'].split(',') or row['ID'].startswith(container):
            return False
    return True

def main():
    p=argparse.ArgumentParser();p.add_argument('--container',default='glm53-flash-tf-trial');p.add_argument('--floor-gib',type=float,default=5);p.add_argument('--self-test',action='store_true');a=p.parse_args()
    if a.self_test:
        assert unsafe(None,5) and unsafe(4*1048576,5) and not unsafe(6*1048576,5)
        print('Memory guard threshold/missing-sample tests passed');return
    tripped=False
    while True:
        try: available=int(next(l.split()[1] for l in pathlib.Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemAvailable:')))
        except Exception: available=None
        if unsafe(available,a.floor_gib):
            tripped=True
        if tripped:
            print(json.dumps({'event':'memory_guard_trip','available_kib':available,'floor_gib':a.floor_gib,'container':a.container}),flush=True)
            try:
                subprocess.run(['docker','kill',a.container],timeout=20,check=False)
            except (OSError,subprocess.TimeoutExpired) as exc:
                print(json.dumps({'event':'memory_guard_kill_retry','error':str(exc)}),flush=True)
            try:
                if target_terminated(a.container):
                    raise SystemExit(1)
            except (OSError,subprocess.TimeoutExpired,ValueError,KeyError,TypeError) as exc:
                print(json.dumps({'event':'memory_guard_verification_retry','error':str(exc)}),flush=True)
        time.sleep(2)
if __name__=='__main__':main()
