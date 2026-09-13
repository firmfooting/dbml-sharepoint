/**
 * dbml-sharepoint deployment script.
 * Generated from: simple.dbml (mtime: 2026-05-04T00:00:00Z)
 * Target site:  https://example.sharepoint.com/sites/test
 * Site role:    default
 * Release tag:  0.1.0-test
 * Schema:       v0.8
 * Deployer:     vdbml-sharepoint/0.1.0
 * Generated at: 2026-05-04T00:00:00Z
 *
 * Paste into the SharePoint browser console and press Enter.
 * Wait for the [SP-DEPLOY] [DONE] log line.
 */
(async () => {
  const SITE_URL  = "https://example.sharepoint.com/sites/test";
  const SITE_ROLE = "default";
  // Set to true and paste again to deploy onto a site the assessment called
  // DEGRADED. Defaults to refusing, like every probe's CONFIRMED flag.
  const ACKNOWLEDGE_DEGRADED = false;
  const RELEASE_TAG = "0.1.0-test";
  const SCHEMA_VERSION = "0.8";
  const ASSESS_REQUIREMENTS = [
  {
    "description": "Operator holds ManageLists on the site",
    "key": "manage_lists_bit",
    "level_on_fail": "BLOCKED"
  },
  {
    "description": "Site is not read-only / locked",
    "key": "site_not_locked",
    "level_on_fail": "BLOCKED"
  },
  {
    "description": "Base template 100 is creatable on the web",
    "key": "list_template_100",
    "level_on_fail": "BLOCKED"
  },
  {
    "description": "List \u0027APP_Project\u0027 is absent or a redeploy target (not a foreign list)",
    "key": "collision:APP_Project",
    "level_on_fail": "BLOCKED"
  },
  {
    "description": "List \u0027APP_Task\u0027 is absent or a redeploy target (not a foreign list)",
    "key": "collision:APP_Task",
    "level_on_fail": "BLOCKED"
  },
  {
    "description": "List \u0027APP_AppSettings\u0027 is absent or a redeploy target (not a foreign list)",
    "key": "collision:APP_AppSettings",
    "level_on_fail": "BLOCKED"
  },
  {
    "description": "Existing list \u0027APP_Project\u0027 is under the 5,000-item list view threshold",
    "key": "item_count:APP_Project",
    "level_on_fail": "WARN"
  },
  {
    "description": "Existing list \u0027APP_Task\u0027 is under the 5,000-item list view threshold",
    "key": "item_count:APP_Task",
    "level_on_fail": "WARN"
  },
  {
    "description": "Existing list \u0027APP_AppSettings\u0027 is under the 5,000-item list view threshold",
    "key": "item_count:APP_AppSettings",
    "level_on_fail": "WARN"
  },
  {
    "description": "Existing list \u0027APP_Project\u0027 carries this declaration\u0027s exact provenance marker",
    "key": "provenance_marker:APP_Project",
    "level_on_fail": "BLOCKED"
  },
  {
    "description": "Existing list \u0027APP_Task\u0027 carries this declaration\u0027s exact provenance marker",
    "key": "provenance_marker:APP_Task",
    "level_on_fail": "BLOCKED"
  },
  {
    "description": "Existing list \u0027APP_AppSettings\u0027 carries this declaration\u0027s exact provenance marker",
    "key": "provenance_marker:APP_AppSettings",
    "level_on_fail": "BLOCKED"
  },
  {
    "description": "Site regional time zone is the users\u0027 zone (dates are stored and shown in it, and the pack\u0027s `today` windows are read against its day)",
    "key": "time_zone",
    "level_on_fail": "WARN"
  },
  {
    "description": "Operator holds ManagePermissions",
    "key": "manage_permissions_bit",
    "level_on_fail": "BLOCKED"
  },
  {
    "description": "CSOM ProcessQuery available (group owner correction)",
    "key": "process_query",
    "level_on_fail": "WARN"
  },
  {
    "description": "SP.Field.CustomFormatter property surface present",
    "key": "custom_formatter_surface",
    "level_on_fail": "WARN"
  },
  {
    "description": "ClientFormCustomFormatter property surface present",
    "key": "form_formatter_surface",
    "level_on_fail": "WARN"
  },
  {
    "description": "Service-managed version auto-trim does not override declared limits",
    "key": "version_trim_mode",
    "level_on_fail": "WARN"
  }
];
  const ASSESS_TARGETS = {
  "base_templates": [
    100
  ],
  "declares_column_formatting": true,
  "declares_form_formatting": true,
  "declares_groups": true,
  "declares_prevent_deletion": false,
  "declares_seal": false,
  "declares_versioning": true,
  "group_renames": [],
  "index_change_ceiling": 20000,
  "level_renames": [],
  "library_folders": [],
  "list_display_titles": [
    [
      "APP_Project",
      [
        [
          "SortOrder",
          "Sort Order"
        ]
      ]
    ],
    [
      "APP_Task",
      [
        [
          "DueDate",
          "Due Date"
        ]
      ]
    ]
  ],
  "list_markers": [
    [
      "APP_Project",
      "Provisioned by dbml-sharepoint from simple-test for list Project."
    ],
    [
      "APP_Task",
      "Provisioned by dbml-sharepoint from simple-test for list Task."
    ],
    [
      "APP_AppSettings",
      "Provisioned by dbml-sharepoint from simple-test for list AppSettings."
    ]
  ],
  "list_renames": [],
  "list_titles": [
    "APP_Project",
    "APP_Task",
    "APP_AppSettings"
  ],
  "list_unique_columns": [],
  "list_view_threshold": 5000,
  "requires_manage_permissions": true,
  "uses_today": true
};
  const ASSESS_NOT_ASSESSABLE = [
  "Power Automate / Power Apps inventory (lives in Power Platform APIs, no SharePoint REST surface from site context)",
  "Audit settings (SSOM-only; not exposed via CSOM/REST)",
  "Information-barrier segments and mode (tenant-admin only)",
  "Authoritative tenant sharing capability and storage quota ceilings (tenant-admin SiteProperties)",
  "Retention POLICY coverage of the site (only inferable via the Preservation Hold Library signal)",
  "Webhook subscription enumeration (bound to the creating app identity)",
  "Edit-form column-description suppression (SharePoint platform behaviour)",
  "[$Created] view-field resolution in formatters (tenant/locale dependent)",
  "Format-pane JSON display encoding (renders identically either way)"
];

  const log = (level, msg) => console.log(`[SP-DEPLOY] [${level}] ${msg}`);
  // Baked in at build time from the dbml-sharepoint.env this run read (or
  // that it read none) -- a log() line, not a header comment, because the
  // operator pastes back the console transcript, not the file.
  log('INFO', "No dbml-sharepoint.env file was read.");
  const RUN_STARTED_AT = Date.now();
  // Phase timings record on every run (cheap); they only PRINT under
  // DEBUG (declared in the shared HTTP partial included below).
  const phaseTimings = {};
  let currentPhaseLabel = null;
  let currentPhaseT0 = 0;
  const markPhase = (label) => {
    if (currentPhaseLabel) {
      phaseTimings[currentPhaseLabel] = (phaseTimings[currentPhaseLabel] || 0) + (Date.now() - currentPhaseT0);
    }
    currentPhaseLabel = label;
    currentPhaseT0 = Date.now();
  };
  const summary = {
    listsCreated: [],
    listsRenamed: [],
    levelsRenamed: [],
    groupsRenamed: [],
    listsSkipped: [],
    // Declared library folders, labelled `<list>/<folder>`, by outcome.
    foldersCreated: [],
    foldersVerified: [],
    columnsCreated: 0,
    columnsSkipped: 0,
    errors: [],
    // The logging phase's OWN failure list, deliberately not `errors`.
    // `errors` is the abort bus every phase gate reads, and the registers
    // this deploy maintains must never depend on the logs that document
    // them: a change row that would not write must not stop a deploy that
    // otherwise succeeded. Declared here, beside `errors`, so the summary
    // has one shape whether or not the logging phase renders.
    loggingFailures: [],
    releaseTag: RELEASE_TAG,
    schemaVersion: SCHEMA_VERSION,
  };


