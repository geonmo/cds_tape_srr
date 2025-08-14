import subprocess
import json
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import requests

app = FastAPI()

def run_podman_command(cmd: list) -> str:
    """podman exec 명령 실행 후 결과 문자열 리턴"""
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Command {' '.join(cmd)} failed: {result.stderr}")
    return result.stdout.strip()

def get_accounting_report() -> dict:
    """eos accounting report -f 결과 JSON 로드"""
    output = run_podman_command([
        "eos", "accounting", "report", "-f"
    ])
    # 명령어 결과가 이미 JSON 형식일 때 바로 파싱
    return json.loads(output)

def get_space_info() -> dict:
    """eos space ls -m 결과에서 필요한 값 추출"""
    output = run_podman_command([
        "eos", "space", "ls", "-m"
    ])
    # key=value 형식으로 split
    parts = output.split()
    info = {}
    for p in parts:
        if "=" in p:
            k, v = p.split("=", 1)
            info[k] = v
    return info

@app.get("/storage")
def get_storage_info(output="web"):
    # 1. accounting report JSON 읽기
    report = get_accounting_report()

    # 2. space ls -m 결과 읽기
    space_info = get_space_info()

    # 3. 사용량/파일 수 계산
    try:
        usedbytes = int(space_info.get("sum.stat.statfs.usedbytes", 0))
        usedfiles = int(space_info.get("sum.stat.usedfiles", 0))

        # usedbytes 계산식 적용: *12/18
        usedbytes_modified = int(usedbytes * 12 / 18)

        # 4. JSON 값 교체
        report["storageservice"]["storagecapacity"]["online"]["usedsize"] = usedbytes_modified
        if report["storageservice"]["storageshares"]:
            report["storageservice"]["storageshares"][0]["usedsize"] = usedbytes_modified
            report["storageservice"]["storageshares"][0]["numberoffiles"] = usedfiles

    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

    if output=="stdout":
        return(report)
    # 5. 결과 리턴
    return JSONResponse(content=json.loads(json.dumps(report,indent=4,ensure_ascii=False)))

if __name__ == "__main__":
    print(json.dumps(get_storage_info(output="stdout"),indent=4, ensure_ascii=False))
