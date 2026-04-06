import json
import datetime as dt
import subprocess
from pathlib import Path

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
# 📦 NEXUS
# =========================================================
NEXUS_URL = "https://alm-latam-assurance.dev.echonet/nexus/service/rest/v1/components"
NEXUS_REPO = "ssc_devops_tools"

NEXUS_DOWNLOAD_BASE = "https://alm-latam-assurance.dev.echonet/nexus/repository/ssc_devops_tools"

NEXUS_API_KEY = "a79eae5b-1b06-34e4-9682-733f3347f314"
NEXUS_AUTH_B64 = "ajEzMzk50jZhMTZkODIZYTM5ZTRkZjcxNTE2MzA2NGEwMWF1MzRk"

# =========================================================
# 📁 WORKSPACE
# =========================================================
WORKSPACE_DIR = Path.cwd()
CACHE_DIR = WORKSPACE_DIR / "dora-cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def clean_view_name(view: str) -> str:
    return view.replace("view/", "").replace(" ", "_")


def get_view_file(view: str) -> Path:
    return CACHE_DIR / f"{clean_view_name(view)}.json"


# =========================================================
# 📥 DOWNLOAD (TU VERSION)
# =========================================================
def download_cache_from_nexus(view: str) -> None:
    # 🔥 Limpia TODO el cache (como pediste)
    subprocess.run(["rm", "-rf", "*"], cwd=CACHE_DIR, check=True)

    file = get_view_file(view)
    view_name = clean_view_name(view)

    url = f"{NEXUS_DOWNLOAD_BASE}/dora-cache/{view_name}.json"

    print(f"⬇️ Descargando cache de {view}...")

    cmd = [
        "curl",
        "--location",
        "--request", "GET",
        url,
        "--output", str(file),
        "--silent",
        "--fail"
    ]

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    if result.returncode != 0:
        print(f"⚠️ No existe cache en Nexus ({view})")
        if file.exists():
            file.unlink()
    else:
        print("✅ Cache descargado correctamente")

    # Debug
    ls_result = subprocess.run(
        ["ls", "-lta"],
        cwd=CACHE_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    print(ls_result.stdout)
    if ls_result.stderr:
        print(ls_result.stderr)


# =========================================================
# 📤 UPLOAD
# =========================================================
def upload_cache_to_nexus(view: str) -> None:
    file = get_view_file(view)
    view_name = clean_view_name(view)

    print(f"\n⬆️ Subiendo cache de {view}...")

    if not file.exists() or file.stat().st_size == 0:
        print("❌ Archivo inválido:", file)
        return

    cmd = [
        "curl",
        "--location",
        "--request", "POST",
        f"{NEXUS_URL}?repository={NEXUS_REPO}",
        "--header", f"X-NuGet-ApiKey: {NEXUS_API_KEY}",
        "--header", f"Authorization: Basic {NEXUS_AUTH_B64}",
        "--form", f'raw.directory="dora-cache"',
        "--form", f'raw.asset1=@"{file}"',
        "--form", f'raw.asset1.filename="{view_name}.json"',
    ]

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    print(result.stdout)
    print(result.stderr)


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


def fetch_builds_since(job_url: str, last_build: int):
    builds = fetch_all_builds(job_url)
    return [b for b in builds if b["number"] > last_build]


def get_builds_smart(job_url: str, cache: dict):
    try:
        latest = get_last_build_number(job_url)
    except:
        return []

    if job_url not in cache:
        builds = fetch_all_builds(job_url)
        cache[job_url] = {"last": latest, "builds": builds}
        return builds

    if cache[job_url]["last"] == latest:
        return cache[job_url]["builds"]

    new_builds = fetch_builds_since(job_url, cache[job_url]["last"])

    cache[job_url]["builds"].extend(new_builds)
    cache[job_url]["last"] = latest

    return new_builds


# =========================================================
# 📊 MÉTRICAS
# =========================================================
def calculate_metrics_for_view(view: str):
    print(f"\n🔍 Procesando {view}...")

    download_cache_from_nexus(view)

    file = get_view_file(view)
    if file.exists() and file.stat().st_size > 0:
        with open(file, "r") as f:
            previous_data = json.load(f)
        cache_data = previous_data.get("jobs", {})
    else:
        cache_data = {}

    jobs = get_jobs_from_view(view)

    all_builds = []

    for job in jobs:
        try:
            builds = get_builds_smart(job, cache_data)

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

    metrics = {
        "view": view,
        "total_jobs": len(jobs),
        "total_builds": len(all_builds),
        "deployments": len(success),
        "failure_rate": (len(failed) / len(all_builds) * 100) if all_builds else 0,
        "deploys_per_day": deploys_per_day
    }

    result = {
        "metrics": metrics,
        "jobs": cache_data
    }

    print(f"💾 Guardando archivo en: {file}")
    with open(file, "w") as f:
        json.dump(result, f, indent=2)

    upload_cache_to_nexus(view)

    return metrics


# =========================================================
# 🌐 HTML REPORT
# =========================================================
def generate_html_report(results):
    html_file = WORKSPACE_DIR / "report.html"

    print(f"🌐 Generando reporte HTML: {html_file}")

    html = """
    <html>
    <head>
        <title>DORA Metrics</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    </head>
    <body>
        <h1>DORA Metrics Report</h1>
    """

    for i, r in enumerate(results):
        labels = list(r["deploys_per_day"].keys())
        values = list(r["deploys_per_day"].values())

        html += f"""
        <h2>{r['view']}</h2>
        <p>Deployments: {r['deployments']}</p>
        <p>Failure Rate: {r['failure_rate']:.2f}%</p>
        <canvas id="chart{i}"></canvas>

        <script>
        new Chart(document.getElementById('chart{i}'), {{
            type: 'line',
            data: {{
                labels: {labels},
                datasets: [{{
                    label: 'Deploys',
                    data: {values}
                }}]
            }}
        }});
        </script>
        """

    html += "</body></html>"

    with open(html_file, "w") as f:
        f.write(html)


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

    print("\n📊 RESULTADO FINAL:")
    print(json.dumps(results, indent=2))

    generate_html_report(results)


if __name__ == "__main__":
    main()