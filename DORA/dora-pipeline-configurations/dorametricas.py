import sys
import json
import datetime as dt
from typing import List, Dict, Any

import requests
from requests.auth import HTTPBasicAuth


# =========================
# 🔧 CONFIGURACIÓN
# =========================
JENKINS_URL = "https://alm-latam-assurance.dev.echonet/jenkins"
JENKINS_USER = "j13399"
JENKINS_API_TOKEN = "118f321bb3320e8d99d95eb4719653afbd"

DAYS_BACK = 30  # ventana de tiempo


# =========================
# 📂 VISTAS
# =========================
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


# =========================
# 🌐 PROXY
# =========================
PROXY = {
    "http": "http://172.17.89.1:8080",
    "https": "http://172.17.89.1:8080",
}

PROXY = {k: v for k, v in PROXY.items() if v}


# =========================
# 🔐 AUTH
# =========================
AUTH = HTTPBasicAuth(JENKINS_USER, JENKINS_API_TOKEN)


# =========================
# 🧰 UTILIDADES
# =========================
def is_within_days(timestamp_ms: int, days: int) -> bool:
    build_time = dt.datetime.fromtimestamp(timestamp_ms / 1000)
    now = dt.datetime.now()
    return (now - build_time).days <= days


# =========================
# 📡 JENKINS API
# =========================
def get_view_jobs(view: str) -> List[Dict[str, Any]]:
    url = f"{JENKINS_URL}/{view}/api/json?tree=jobs[name,url,_class]"
    response = requests.get(url, auth=AUTH, proxies=PROXY)
    response.raise_for_status()
    return response.json().get("jobs", [])


def get_all_jobs(job_url: str) -> List[str]:
    jobs = []

    url = f"{job_url}/api/json?tree=jobs[name,url,_class]"
    response = requests.get(url, auth=AUTH, proxies=PROXY)
    response.raise_for_status()

    for item in response.json().get("jobs", []):
        job_class = item.get("_class", "")
        url = item.get("url")

        if "Folder" in job_class:
            jobs.extend(get_all_jobs(url))
        else:
            jobs.append(url)

    return jobs


def get_jobs_from_view(view: str) -> List[str]:
    jobs = []

    for item in get_view_jobs(view):
        job_class = item.get("_class", "")
        url = item.get("url")

        if "Folder" in job_class:
            jobs.extend(get_all_jobs(url))
        else:
            jobs.append(url)

    return jobs


def get_builds(job_url: str) -> List[Dict[str, Any]]:
    url = f"{job_url}/api/json?tree=builds[number,result,timestamp]"
    response = requests.get(url, auth=AUTH, proxies=PROXY)
    response.raise_for_status()
    return response.json().get("builds", [])


# =========================
# 📊 MÉTRICAS DORA
# =========================
def calculate_metrics_for_view(view: str) -> Dict[str, Any]:
    print(f"\n🔍 Procesando {view}...")

    jobs = get_jobs_from_view(view)
    print(f"   Jobs encontrados: {len(jobs)}")

    all_builds = []

    for job in jobs:
        try:
            builds = get_builds(job)

            # Filtrar por tiempo
            builds = [b for b in builds if is_within_days(b["timestamp"], DAYS_BACK)]

            all_builds.extend(builds)

        except Exception as e:
            print(f"   ⚠️ Error en job {job}: {e}")

    total_builds = len(all_builds)
    success_builds = [b for b in all_builds if b.get("result") == "SUCCESS"]
    failed_builds = [b for b in all_builds if b.get("result") != "SUCCESS"]

    # Deployment Frequency (por día)
    deploys_per_day = {}

    for b in success_builds:
        date = dt.datetime.fromtimestamp(b["timestamp"] / 1000).strftime("%Y-%m-%d")
        deploys_per_day[date] = deploys_per_day.get(date, 0) + 1

    # Failure Rate
    failure_rate = (len(failed_builds) / total_builds * 100) if total_builds else 0

    return {
        "view": view,
        "total_jobs": len(jobs),
        "total_builds": total_builds,
        "deployments": len(success_builds),
        "failure_rate": round(failure_rate, 2),
        "deploys_per_day": deploys_per_day,
    }


# =========================
# 🚀 MAIN
# =========================
def main():
    results = []

    for view in COUNTRY_FOLDERS:
        try:
            metrics = calculate_metrics_for_view(view)
            results.append(metrics)
        except Exception as e:
            print(f"❌ Error procesando {view}: {e}")

    print("\n📊 RESULTADO FINAL:\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()