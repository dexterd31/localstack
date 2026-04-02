import json
import datetime as dt
import subprocess
from pathlib import Path
from typing import Dict, Any

import requests
from requests.auth import HTTPBasicAuth


# =========================================================
# 🔧 CONFIG
# =========================================================
JENKINS_URL = "https://alm-latam-assurance.dev.echonet/jenkins"
JENKINS_USER = "j13399"
JENKINS_API_TOKEN = "118f321bb3320e8d99d95eb4719653afbd"

DAYS_BACK = 30

COUNTRY_FOLDERS = [
    "view/Automation",
    "view/Chile",
    "view/Colombia",
    "view/Devops LAM",
    "view/KAFKA",
    "view/LAM Microservices",
    "view/PIMS",
    "view/PreProd-Chile",
]

PROXY = {
    "http": "http://172.17.89.1:8080",
    "https": "http://172.17.89.1:8080",
}
PROXY = {k: v for k, v in PROXY.items() if v}

AUTH = HTTPBasicAuth(JENKINS_USER, JENKINS_API_TOKEN)


# =========================================================
# 📦 NEXUS
# =========================================================
NEXUS_URL = "https://alm-latam-assurance.dev.echonet/nexus/service/rest/v1/components"
NEXUS_REPO = "ssc_devops_tools"
NEXUS_DOWNLOAD_BASE = "https://alm-latam-assurance.dev.echonet/nexus/repository/ssc_devops_tools"

NEXUS_API_KEY = "a79eae5b-1b06-34e4-9682-733f3347f314"
NEXUS_AUTH_B64 = "ajEzMzk50jZhMTZkODIZYTM5ZTRkZjcxNTE2MzA2NGEWMWF1MZRK"


# =========================================================
# 📁 CACHE
# =========================================================
CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)


def clean_view_name(view: str) -> str:
    return view.replace("view/", "").replace(" ", "_")


def get_view_cache_file(view: str) -> Path:
    return CACHE_DIR / f"{clean_view_name(view)}.json"


def load_view_cache(view: str) -> Dict[str, Any]:
    """
    Carga cache local de forma segura.
    Si el archivo está corrupto o vacío → lo ignora.
    """
    file = get_view_cache_file(view)

    if not file.exists():
        return {"jobs": {}, "timestamp": None}

    try:
        with open(file, "r") as f:
            return json.load(f)
    except Exception:
        print(f"⚠️ Cache inválido en {view}, se ignora")
        return {"jobs": {}, "timestamp": None}


def save_view_cache(view: str, cache_data: Dict[str, Any]) -> None:
    file = get_view_cache_file(view)
    cache_data["timestamp"] = dt.datetime.now().isoformat()

    with open(file, "w") as f:
        json.dump(cache_data, f)


# =========================================================
# 📥 DOWNLOAD NEXUS (ROBUSTO)
# =========================================================
def download_cache_from_nexus(view: str) -> None:
    """
    Descarga cache desde Nexus.
    - Si 404 → continúa
    - Si archivo inválido → lo elimina
    """
    file = get_view_cache_file(view)
    view_name = clean_view_name(view)

    print(f"⬇️ Descargando cache de {view}...")

    url = f"{NEXUS_DOWNLOAD_BASE}/dora-cache/{view_name}/{view_name}.json"

    cmd = [
        "curl",
        "--location",
        "--request", "GET",
        url,
        "--header", f"Authorization: Basic {NEXUS_AUTH_B64}",
        "--output", str(file),
        "--silent",
        "--fail"  # 🔥 clave para detectar 404
    ]

    result = subprocess.run(cmd)

    if result.returncode != 0:
        print(f"⚠️ Cache no existe en Nexus para {view} (probable 404)")

        if file.exists():
            file.unlink()  # eliminar basura


# =========================================================
# 📤 UPLOAD NEXUS
# =========================================================
def upload_cache_to_nexus(view: str) -> None:
    file = get_view_cache_file(view)
    view_name = clean_view_name(view)

    print(f"⬆️ Subiendo cache de {view}...")

    cmd = [
        "curl",
        "--location",
        "--request", "POST",
        f"{NEXUS_URL}?repository={NEXUS_REPO}",
        "--header", f"X-NuGet-ApiKey: {NEXUS_API_KEY}",
        "--header", f"Authorization: Basic {NEXUS_AUTH_B64}",
        "--form", f'raw.directory=dora-cache/{view_name}',
        "--form", f'raw.asset1=@{file}',
        "--form", f'raw.asset1.filename={view_name}.json',
    ]

    subprocess.run(cmd)


# =========================================================
# 🧰 UTIL
# =========================================================
def is_within_days(timestamp_ms: int, days: int) -> bool:
    build_time = dt.datetime.fromtimestamp(timestamp_ms / 1000)
    return (dt.datetime.now() - build_time).days <= days


# =========================================================
# 📡 JENKINS
# =========================================================
def get_view_jobs(view: str):
    url = f"{JENKINS_URL}/{view}/api/json?tree=jobs[name,url,_class]"
    r = requests.get(url, auth=AUTH, proxies=PROXY)
    r.raise_for_status()
    return r.json().get("jobs", [])


def get_all_jobs(job_url: str):
    jobs = []
    url = f"{job_url}/api/json?tree=jobs[name,url,_class]"
    r = requests.get(url, auth=AUTH, proxies=PROXY)
    r.raise_for_status()

    for item in r.json().get("jobs", []):
        if "Folder" in item.get("_class", ""):
            jobs.extend(get_all_jobs(item["url"]))
        else:
            jobs.append(item["url"])

    return jobs


def get_jobs_from_view(view: str):
    jobs = []
    for item in get_view_jobs(view):
        if "Folder" in item.get("_class", ""):
            jobs.extend(get_all_jobs(item["url"]))
        else:
            jobs.append(item["url"])
    return jobs


def get_last_build_number(job_url: str) -> int:
    url = f"{job_url}/api/json?tree=lastBuild[number]"
    r = requests.get(url, auth=AUTH, proxies=PROXY)
    r.raise_for_status()
    return r.json().get("lastBuild", {}).get("number", 0)


def fetch_all_builds(job_url: str):
    url = f"{job_url}/api/json?tree=builds[number,result,timestamp]"
    r = requests.get(url, auth=AUTH, proxies=PROXY)
    r.raise_for_status()
    return r.json().get("builds", [])


def get_builds_smart(job_url: str, view_cache: dict):
    jobs_cache = view_cache["jobs"]

    try:
        latest_build = get_last_build_number(job_url)
    except:
        return []

    if job_url not in jobs_cache:
        print(f"🆕 Nuevo job: {job_url}")
        builds = fetch_all_builds(job_url)

        jobs_cache[job_url] = {
            "last_build": latest_build,
            "builds": builds
        }
        return builds

    cached = jobs_cache[job_url]

    if cached["last_build"] == latest_build:
        return cached["builds"]

    print(f"♻️ Actualizando job: {job_url}")
    builds = fetch_all_builds(job_url)

    jobs_cache[job_url] = {
        "last_build": latest_build,
        "builds": builds
    }

    return builds


# =========================================================
# 📊 MÉTRICAS
# =========================================================
def calculate_metrics_for_view(view: str):
    print(f"\n🔍 Procesando {view}...")

    download_cache_from_nexus(view)
    view_cache = load_view_cache(view)

    jobs = get_jobs_from_view(view)
    print(f"   Jobs encontrados: {len(jobs)}")

    all_builds = []

    for job in jobs:
        try:
            builds = get_builds_smart(job, view_cache)
            builds = [b for b in builds if is_within_days(b["timestamp"], DAYS_BACK)]
            all_builds.extend(builds)
        except Exception as e:
            print(f"⚠️ Error en job {job}: {e}")

    save_view_cache(view, view_cache)
    upload_cache_to_nexus(view)

    total = len(all_builds)
    success = [b for b in all_builds if b.get("result") == "SUCCESS"]
    failed = [b for b in all_builds if b.get("result") != "SUCCESS"]

    deploys_per_day = {}
    for b in success:
        d = dt.datetime.fromtimestamp(b["timestamp"] / 1000).strftime("%Y-%m-%d")
        deploys_per_day[d] = deploys_per_day.get(d, 0) + 1

    failure_rate = (len(failed) / total * 100) if total else 0

    return {
        "view": view,
        "total_jobs": len(jobs),
        "total_builds": total,
        "deployments": len(success),
        "failure_rate": round(failure_rate, 2),
        "deploys_per_day": deploys_per_day,
    }


# =========================================================
# 🚀 MAIN
# =========================================================
def main():
    results = []

    for view in COUNTRY_FOLDERS:
        try:
            metrics = calculate_metrics_for_view(view)
            results.append(metrics)
        except Exception as e:
            print(f"❌ Error en {view}: {e}")

    print("\n📊 RESULTADO FINAL:\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()