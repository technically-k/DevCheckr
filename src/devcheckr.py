# DevCheckr - GitHub Audit Tool
# Copyright (c) 2025 Kareem
# Licensed under the MIT License
# See LICENSE for full details.


import os
import webbrowser
import customtkinter as ctk
from tkinter import filedialog, messagebox
from azure.devops.connection import Connection
from msrest.authentication import BasicAuthentication
from azure.devops.v7_0.git.models import GitQueryCommitsCriteria
from datetime import datetime, timedelta
from pathlib import Path
import requests

FAIL_THRESHOLD = 30
REPO_INACTIVITY_DAYS = 90
PIPELINE_INACTIVITY_DAYS = 60

ctk.set_appearance_mode("system")
ctk.set_default_color_theme("blue")

class DevOpsAuditApp:
    def __init__(self, root):
        self.report_lines = []
        self.root = root
        self.root.title("DevOps Audit Tool")
        self.root.geometry("920x880")

        self.description = ctk.CTkLabel(
            root,
            text=(
                "🔧 DevOps Audit Tool\n\n"
                "Easily audit your Azure DevOps or GitHub projects:\n"
                "• Monitor repository activity\n"
                "• Check branch policies\n"
                "• Analyze pipelines/workflows\n"
                "• Export sleek HTML reports"
            ),
            justify="left",
            wraplength=800,
            font=("Segoe UI", 14, "normal")
        )
        self.description.pack(padx=20, pady=(20, 10))

        self.card = ctk.CTkFrame(root, corner_radius=15)
        self.card.pack(pady=(10, 15), padx=20, fill="x")

        self.platform_label = ctk.CTkLabel(self.card, text="Select Platform:", font=("Segoe UI", 12))
        self.platform_label.pack(pady=(15, 5), anchor="w", padx=20)

        self.platform_var = ctk.StringVar(value="Azure DevOps")
        self.platform_var.trace_add("write", self.update_labels)
        self.platform_dropdown = ctk.CTkOptionMenu(self.card, values=["Azure DevOps", "GitHub"], variable=self.platform_var)
        self.platform_dropdown.pack(padx=20, fill="x")

        self.org_label = ctk.CTkLabel(self.card, text="Organization URL:", font=("Segoe UI", 12))
        self.org_label.pack(pady=(15, 5), anchor="w", padx=20)

        self.org_entry = ctk.CTkEntry(self.card, width=650)
        self.org_entry.pack(padx=20, fill="x")

        self.pat_label = ctk.CTkLabel(self.card, text="Personal Access Token (PAT):", font=("Segoe UI", 12))
        self.pat_label.pack(pady=(15, 5), anchor="w", padx=20)

        self.pat_entry = ctk.CTkEntry(self.card, width=650, show="*")
        self.pat_entry.pack(padx=20, fill="x")

        self.pat_info_link = ctk.CTkLabel(
            self.card,
            text="🔗 Generate GitHub Token (must include 'repo' scope for private repos)",
            text_color="#1f6feb",
            cursor="hand2",
            font=("Segoe UI", 11, "underline")
        )
        self.pat_info_link.pack(padx=20, anchor="w")
        self.pat_info_link.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/settings/tokens"))

        self.save_var = ctk.BooleanVar()
        self.save_check = ctk.CTkCheckBox(self.card, text="Save HTML Report", variable=self.save_var)
        self.save_check.pack(pady=(15, 5), padx=20, anchor="w")

        self.choose_button = ctk.CTkButton(self.card, text="📁 Choose Save Location", command=self.choose_location)
        self.choose_button.pack(pady=5, padx=20)

        self.run_button = ctk.CTkButton(self.card, text="▶ Run Audit", command=self.run_audit, height=40, font=("Segoe UI", 13, "bold"))
        self.run_button.pack(pady=(10, 20), padx=20)

        self.output_label = ctk.CTkLabel(root, text="📊 Audit Output:", font=("Segoe UI", 13, "bold"))
        self.output_label.pack(pady=(10, 5), padx=20, anchor="w")

        self.output = ctk.CTkTextbox(root, width=850, height=400, corner_radius=12, font=("Consolas", 12))
        self.output.pack(padx=20, pady=10)

        self.output_dir = Path.cwd()
        self.update_labels()

    def update_labels(self, *args):
        platform = self.platform_var.get()
        if platform == "GitHub":
            self.org_label.configure(text="GitHub Org or Username (or paste full URL):")
            self.pat_label.configure(text="GitHub Personal Access Token (PAT):")
            self.pat_info_link.pack(padx=20, anchor="w")
        else:
            self.org_label.configure(text="Azure DevOps Organization URL:")
            self.pat_label.configure(text="Azure DevOps Personal Access Token (PAT):")
            self.pat_info_link.pack_forget()

    def choose_location(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_dir = Path(folder)

    def log(self, line, tag=None):
        self.output.insert("end", line + "\n")
        self.output.see("end")
        if self.save_var.get():
            self.report_lines.append(line)

    def run_audit(self):
        self.output.delete("1.0", "end")
        self.report_lines = []

        platform = self.platform_var.get()
        org_url = self.org_entry.get().strip()
        pat = self.pat_entry.get().strip()

        if not org_url or not pat:
            messagebox.showerror("Missing Input", "Please enter both Organization/Username and PAT.")
            return

        self.log(f"🔍 Running audit for {platform}...")

        try:
            if platform == "Azure DevOps":
                self.run_azure_devops_scan(org_url, pat)
            elif platform == "GitHub":
                self.run_github_scan(org_url, pat)
        except Exception as e:
            self.log(f"❌ Error during scan: {e}")

        if self.save_var.get() and self.report_lines:
            now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            output_file = self.output_dir / f"devops_audit_{now}.html"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write("<br>".join(self.report_lines))
            self.log(f"✅ Report saved to {output_file}")

    def run_azure_devops_scan(self, org_url, pat):
        credentials = BasicAuthentication("", pat)
        connection = Connection(base_url=org_url, creds=credentials)
        core_client = connection.clients.get_core_client()
        git_client = connection.clients.get_git_client()

        self.log("🔗 Connected to Azure DevOps")

        projects = core_client.get_projects()
        if not projects:
            self.log("⚠️ No projects found.")
            return

        total = 0
        inactive = 0
        active = 0

        for project in projects:
            self.log(f"\n📁 Project: {project.name}")
            repos = git_client.get_repositories(project.name)
            for repo in repos:
                total += 1
                self.log(f"  📦 Repository: {repo.name}")
                self.log(f"    Default Branch: {repo.default_branch or 'N/A'}")

                inactivity_cutoff = datetime.utcnow() - timedelta(days=REPO_INACTIVITY_DAYS)
                criteria = GitQueryCommitsCriteria(from_date=inactivity_cutoff.isoformat())
                commits = git_client.get_commits(repository_id=repo.id, project=project.name, search_criteria=criteria)

                if not commits:
                    self.log(f"    ⚠️ No commits in last {REPO_INACTIVITY_DAYS} days")
                    inactive += 1
                else:
                    latest = commits[0].author.date.strftime("%Y-%m-%d")
                    self.log(f"    ✅ Recent commit: {latest}")
                    active += 1

        summary = (
            f"\n📊 Audit Summary\n"
            f"   • Total Repos: {total}\n"
            f"   • Inactive Repos: {inactive}\n"
            f"   • Recently Active: {active}\n\n"
        )
        self.output.insert("1.0", summary)
        if self.save_var.get():
            self.report_lines.insert(0, summary.replace('\n', '<br>'))

    def run_github_scan(self, org_url, pat):
        self.log("🔗 Connecting to GitHub...")
        headers = {
            "Authorization": f"token {pat}",
            "Accept": "application/vnd.github+json"
        }

        name = org_url.rstrip("/").split("/")[-1]
        is_user = False

        repo_url = f"https://api.github.com/orgs/{name}/repos?per_page=100&type=all"
        response = requests.get(repo_url, headers=headers)

        if response.status_code == 404:
            self.log("🔁 Falling back to user repo scan...")
            is_user = True
            repo_url = f"https://api.github.com/users/{name}/repos?per_page=100&type=all"
            response = requests.get(repo_url, headers=headers)

        if response.status_code != 200:
            self.log(f"❌ Failed to fetch repos: {response.status_code} - {response.text}")
            return

        repos = []
        page = 1
        while True:
            paged_url = f"{repo_url}&page={page}"
            resp = requests.get(paged_url, headers=headers)
            if resp.status_code != 200:
                break
            page_data = resp.json()
            if not page_data:
                break
            repos.extend(page_data)
            page += 1

        self.log(f"📦 Total repos returned: {len(repos)}")

        if not repos:
            self.log("⚠️ No repositories found. Make sure your token has access to private repos.")
            return

        inactive = 0
        active = 0

        for repo in repos:
            repo_name = repo["name"]
            private = "🔐 Private" if repo["private"] else "🌐 Public"
            last_push = repo["pushed_at"]
            default_branch = repo.get("default_branch", "N/A")
            last_push_date = datetime.strptime(last_push, "%Y-%m-%dT%H:%M:%SZ")

            self.log(f"\n📦 Repo: {repo_name} ({private})")
            self.log(f"   Default Branch: {default_branch}")
            self.log(f"   Last Push: {last_push_date.strftime('%Y-%m-%d')}")

            if datetime.utcnow() - last_push_date > timedelta(days=REPO_INACTIVITY_DAYS):
                self.log(f"   ⚠️ Inactive > {REPO_INACTIVITY_DAYS} days")
                inactive += 1
            else:
                self.log("   ✅ Recently active")
                active += 1

        summary = (
            f"\n📊 Audit Summary\n"
            f"   • Total Repos: {len(repos)}\n"
            f"   • Inactive Repos: {inactive}\n"
            f"   • Recently Active: {active}\n\n"
        )
        self.output.insert("1.0", summary)
        if self.save_var.get():
            self.report_lines.insert(0, summary.replace('\n', '<br>'))

if __name__ == "__main__":
    root = ctk.CTk()
    app = DevOpsAuditApp(root)
    root.mainloop()
