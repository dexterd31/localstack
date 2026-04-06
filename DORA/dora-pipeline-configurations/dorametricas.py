import json
import datetime as dt
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
    "view/Chile",
    "view/Automation",
    "view/Colombia",
    "view/Devops LAM",
    "view/KAFKA",
    "view/LAM Microservices",
    "view/PIMS",
    "view/PreProd-Chile"
]

# =========================================================
# 🌐 PROXY
# =========================================================
PROXY = {
    "http": "http://172.17.89.1:8080",
    "https": "http://172.17.89.1:8080",
}
PROXY = {k: v for k, v in PROXY.items() if v}

# =========================================================
# 🔐 AUTH
# =========================================================
AUTH = HTTPBasicAuth(JENKINS_USER, JENKINS_API_TOKEN)

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


def fetch_all_builds(job_url: str):
    url = f"{job_url}/api/json?tree=builds[number,result,timestamp]"
    r = requests.get(url, auth=AUTH, proxies=PROXY)
    r.raise_for_status()
    return r.json().get("builds", [])


# =========================================================
# 🧠 MTTR
# =========================================================
def calculate_mttr(builds):
    builds_sorted = sorted(builds, key=lambda x: x["timestamp"])

    mttr_times = []
    failure_time = None

    for b in builds_sorted:
        if b.get("result") != "SUCCESS":
            if failure_time is None:
                failure_time = b["timestamp"]

        elif b.get("result") == "SUCCESS" and failure_time:
            recovery_time = b["timestamp"]
            mttr_times.append(recovery_time - failure_time)
            failure_time = None

    if not mttr_times:
        return 0

    return round(sum(mttr_times) / len(mttr_times) / 1000 / 3600, 2)


# =========================================================
# 📊 MÉTRICAS
# =========================================================
def calculate_metrics_for_view(view: str):
    print(f"\n🔍 Procesando {view}...")

    jobs = get_jobs_from_view(view)

    all_builds = []

    for job in jobs:
        try:
            builds = fetch_all_builds(job)

            # Filtrar últimos días
            builds = [
                b for b in builds
                if (dt.datetime.now() - dt.datetime.fromtimestamp(b["timestamp"] / 1000)).days <= DAYS_BACK
            ]

            all_builds.extend(builds)

        except Exception as e:
            print(f"⚠️ Error en {job}: {e}")

    success = [b for b in all_builds if b.get("result") == "SUCCESS"]
    failed = [b for b in all_builds if b.get("result") != "SUCCESS"]

    deploys_per_day = {}
    for b in success:
        d = dt.datetime.fromtimestamp(b["timestamp"] / 1000).strftime("%Y-%m-%d")
        deploys_per_day[d] = deploys_per_day.get(d, 0) + 1

    mttr = calculate_mttr(all_builds)

    metrics = {
        "view": view,
        "total_jobs": len(jobs),
        "total_builds": len(all_builds),
        "deployments": len(success),
        "failure_rate": (len(failed) / len(all_builds) * 100) if all_builds else 0,
        "mttr_hours": mttr,
        "deploys_per_day": deploys_per_day
    }

    # 🔥 LOG TIPO DASHBOARD
    print(f"""
📊 ===== {view} =====
Jobs: {metrics['total_jobs']}
Builds: {metrics['total_builds']}
Deployments: {metrics['deployments']}
Failure Rate: {metrics['failure_rate']:.2f}%
MTTR (hrs): {metrics['mttr_hours']}
========================
""")

    return metrics


# =========================================================
# 🚀 MAIN
# =========================================================
def main():
    results = []

    for view in COUNTRY_FOLDERS:
        try:
            results.append(calculate_metrics_for_view(view))
        except Exception as e:
            print(f"❌ Error en {view}: {e}")

    print("\n✅ Ejecución finalizada correctamente.")


if __name__ == "__main__":
    main()