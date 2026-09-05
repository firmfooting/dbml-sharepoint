# src/dbml_sharepoint/generators/centralloggen.py
"""Render deploy-central-log.js.txt, the central logging sidecar.

The consent-shaped half of the deployment-log feature. A DEPLOY stamps the
central site's list only when site, list and AddListItems all check out,
and notes the absence otherwise; creating a whole site is not a side
effect a register provisioning run may take. This script is the operator's
deliberate act: pasted once from any authenticated page of the tenant, it
creates the central logging site and its deployment-log list (marker-
owned like every list this tool keeps), stamps one provenance row, and
refuses -- creating nothing -- when the paste site is not the parent the
target URL needs.
"""

from dbml_sharepoint import __version__
from dbml_sharepoint.analysis.sidecars import central_log_marker
from dbml_sharepoint.templating import script_env

#: What the CLI writes the script as. `.js.txt` for the reason every other
#: pasteable carries it: a `.js` on Windows is associated with Windows
#: Script Host, and double-clicking one runs it outside the browser.
CENTRAL_LOG_SCRIPT = "deploy-central-log.js.txt"


def generate_central_log_js(
    *,
    central_log_site: str,
    central_log_list: str,
    generated_at: str,
) -> str:
    """The pasteable script that ensures the central site + list exist."""
    return script_env().get_template("central-log.js.j2").render(
        central_log_site=central_log_site,
        central_log_list=central_log_list,
        central_log_marker=central_log_marker(),
        central_site_description=(
            "Central logging for firmfooting applications. Deployment start/"
            "stop/provenance rows from every site this tool provisions."
            f" Provisioned by dbml-sharepoint v{__version__}."
        ),
        generated_at=generated_at,
        deployer_version=__version__,
    )
