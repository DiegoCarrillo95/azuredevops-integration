import base64
import logging
import os

import requests

log = logging.getLogger(__name__)

API_VERSION = "7.1"


class AzDoClient:
    """Azure DevOps REST API client."""

    def __init__(self, *, org=None, project=None, team=None, pat=None):
        self.org = org or os.environ.get("AZDO_ORG")
        self.project = project or os.environ.get("AZDO_PROJECT")
        self.team = team or os.environ.get("AZDO_TEAM")
        pat = pat or os.environ.get("AZDO_PAT")

        if not pat:
            raise ValueError("AZDO_PAT is not set. Set it via environment variable or --pat.")
        if not self.org:
            raise ValueError("AZDO_ORG is not set. Set it via environment variable or --org.")
        if not self.project:
            raise ValueError("AZDO_PROJECT is not set. Set it via environment variable or --project.")

        self._session = requests.Session()
        token = base64.b64encode(f":{pat}".encode()).decode()
        self._session.headers.update({
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
        })

    @property
    def _team_base(self):
        parts = [f"https://dev.azure.com/{self.org}/{self.project}"]
        if self.team:
            parts.append(self.team)
        return "/".join(parts)

    @property
    def _project_base(self):
        return f"https://dev.azure.com/{self.org}/{self.project}"

    def _get(self, url, params=None):
        params = params or {}
        params.setdefault("api-version", API_VERSION)
        log.debug("GET %s", url)
        resp = self._session.get(url, params=params)
        if not resp.ok:
            log.error("GET %s → %s: %s", url, resp.status_code, resp.text[:300])
            resp.raise_for_status()
        return resp.json()

    def _post(self, url, json_body, params=None):
        params = params or {}
        params.setdefault("api-version", API_VERSION)
        log.debug("POST %s", url)
        resp = self._session.post(url, params=params, json=json_body)
        if not resp.ok:
            log.error("POST %s → %s: %s", url, resp.status_code, resp.text[:300])
            resp.raise_for_status()
        return resp.json()

    # ── Iterations / Sprints ───────────────────────────────────────────

    def get_current_iteration(self):
        """Return the current iteration (sprint) for the team, or None."""
        url = f"{self._team_base}/_apis/work/teamsettings/iterations"
        data = self._get(url, {"$timeframe": "current"})
        iterations = data.get("value", [])
        if not iterations:
            return None
        return iterations[0]

    def get_iteration_work_item_ids(self, iteration_id):
        """Return the list of work item IDs in the given iteration."""
        url = f"{self._team_base}/_apis/work/teamsettings/iterations/{iteration_id}/workitems"
        data = self._get(url)
        return [r["target"]["id"] for r in data.get("workItemRelations", []) if "target" in r]

    # ── Work Items ─────────────────────────────────────────────────────

    def get_work_items_batch(self, ids, fields=None):
        """Fetch work item details in batch (max 200 per API call)."""
        if not ids:
            return []

        fields = fields or [
            "System.Id",
            "System.Title",
            "System.State",
            "System.WorkItemType",
            "System.AssignedTo",
            "System.Tags",
            "Microsoft.VSTS.Common.Priority",
            "Microsoft.VSTS.Common.Severity",
            "Microsoft.VSTS.Scheduling.Effort",
        ]

        all_items = []
        # API limits to 200 IDs per call
        for i in range(0, len(ids), 200):
            chunk = ids[i : i + 200]
            url = f"{self._project_base}/_apis/wit/workitemsbatch"
            data = self._post(url, {"ids": chunk, "fields": fields})
            all_items.extend(data.get("value", []))

        return all_items
