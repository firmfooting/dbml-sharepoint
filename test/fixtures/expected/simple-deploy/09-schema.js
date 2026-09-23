  // === Schema definition (rendered from DBML + mapping) ===
  const SCHEMA = {
  "field_defaults": [
    {
      "default_formula": null,
      "default_value": "Open",
      "field": "Status",
      "list": "APP_Project",
      "metadata_type": "SP.FieldChoice"
    },
    {
      "default_formula": null,
      "default_value": "0",
      "field": "SortOrder",
      "list": "APP_Project",
      "metadata_type": "SP.FieldNumber"
    }
  ],
  "folder_assignments": [],
  "form_formatting": [
    {
      "client_form_custom_formatter": "{\"bodyJSONFormatter\":{\"sections\":[{\"displayname\":\"Project\",\"fields\":[\"Title\",\"Status\",\"Sort Order\"]}]}}",
      "list": "APP_Project"
    }
  ],
  "groups": [
    {
      "allow_members_edit_membership": false,
      "allow_request_to_join_leave": false,
      "auto_accept_request_to_join_leave": false,
      "description": "Test group. Provisioned by dbml-sharepoint from simple-test for group List Maintainer.",
      "enroll_enterprise_reader": false,
      "enroll_operator_during_deploy": false,
      "expected_marker": "Provisioned by dbml-sharepoint from simple-test for group List Maintainer.",
      "name": "List Maintainer",
      "only_allow_members_view_membership": false,
      "owner_group": "Site Owners",
      "previous_names": [],
      "require_empty_at_deploy": true
    }
  ],
  "indexed_columns": [
    {
      "field": "Title",
      "list": "APP_Project"
    },
    {
      "field": "DueDate",
      "list": "APP_Task"
    }
  ],
  "list_assignments": [
    {
      "assignments": [
        {
          "level": "Schema Manager",
          "principal": {
            "kind": "group",
            "name": "List Maintainer"
          }
        },
        {
          "level": "Contribute",
          "principal": {
            "kind": "associated_owner_group"
          }
        },
        {
          "level": "Read",
          "principal": {
            "kind": "associated_visitor_group"
          }
        }
      ],
      "break_inheritance": true,
      "list": "APP_Project",
      "reconcile_mode": "exact"
    },
    {
      "assignments": [
        {
          "level": "Schema Manager",
          "principal": {
            "kind": "group",
            "name": "List Maintainer"
          }
        },
        {
          "level": "Contribute",
          "principal": {
            "kind": "associated_owner_group"
          }
        },
        {
          "level": "Read",
          "principal": {
            "kind": "associated_visitor_group"
          }
        }
      ],
      "break_inheritance": true,
      "list": "APP_Task",
      "reconcile_mode": "exact"
    },
    {
      "assignments": [
        {
          "level": "Schema Manager",
          "principal": {
            "kind": "group",
            "name": "List Maintainer"
          }
        },
        {
          "level": "Contribute",
          "principal": {
            "kind": "associated_owner_group"
          }
        },
        {
          "level": "Read",
          "principal": {
            "kind": "associated_visitor_group"
          }
        }
      ],
      "break_inheritance": true,
      "list": "APP_AppSettings",
      "reconcile_mode": "exact"
    }
  ],
  "lists": [
    {
      "base_template": 100,
      "content_types_enabled": false,
      "description": "Parser-fixture projects, each with a status and a sort order. Provisioned by dbml-sharepoint from simple-test for list Project.",
      "disable_attachments": false,
      "enable_minor_versions": false,
      "enable_versioning": true,
      "expected_marker": "Provisioned by dbml-sharepoint from simple-test for list Project.",
      "fields_phase1": [
        {
          "body": {
            "Choices": {
              "results": [
                "Open",
                "Closed"
              ]
            },
            "DefaultValue": "Open",
            "FieldTypeKind": 6,
            "FillInChoice": false,
            "Required": true,
            "Title": "Status",
            "__metadata": {
              "type": "SP.FieldChoice"
            }
          },
          "client_validation_formula": "__dbmlsp_unmanaged__",
          "custom_formatter": "{\"$schema\":\"https://developer.microsoft.com/json-schemas/sp/v2/column-formatting.schema.json\",\"attributes\":{\"class\":\"=if(@currentField == \u0027Open\u0027, \u0027sp-css-backgroundColor-BgLightBlue\u0027, \u0027sp-css-backgroundColor-BgMintGreen\u0027)\"},\"elmType\":\"div\",\"txtContent\":\"@currentField\"}",
          "display_title": "Status",
          "seal": false,
          "title": "Status",
          "validation_formula": "__dbmlsp_unmanaged__",
          "validation_message": "__dbmlsp_unmanaged__"
        },
        {
          "body": {
            "DefaultValue": "0",
            "FieldTypeKind": 9,
            "Required": true,
            "Title": "SortOrder",
            "__metadata": {
              "type": "SP.FieldNumber"
            }
          },
          "client_validation_formula": "__dbmlsp_unmanaged__",
          "custom_formatter": null,
          "display_title": "Sort Order",
          "seal": false,
          "title": "SortOrder",
          "validation_formula": "__dbmlsp_unmanaged__",
          "validation_message": "__dbmlsp_unmanaged__"
        }
      ],
      "folders": [],
      "is_library": false,
      "item_security": null,
      "kind": "List",
      "major_version_limit": 500,
      "prevent_deletion": false,
      "renamed_from": [],
      "title": "APP_Project",
      "title_patch": {
        "Description": "Project name.",
        "Required": true,
        "__metadata": {
          "type": "SP.FieldText"
        }
      },
      "validation_described": "(NOT(Status eq \u0027Closed\u0027) OR SortOrder geq 0)",
      "validation_formula": "=OR([Status]\u003c\u003e\"Closed\",[Sort Order]\u003e=0)",
      "validation_hoisted": [],
      "validation_message": "A closed project needs a non-negative sort order."
    },
    {
      "base_template": 100,
      "content_types_enabled": false,
      "description": "Parser-fixture tasks, each belonging to one project and optionally due on a date. Provisioned by dbml-sharepoint from simple-test for list Task.",
      "disable_attachments": false,
      "enable_minor_versions": false,
      "enable_versioning": true,
      "expected_marker": "Provisioned by dbml-sharepoint from simple-test for list Task.",
      "fields_phase1": [
        {
          "body": {
            "AllowMultipleValues": false,
            "FieldTypeKind": 7,
            "LookupField": "Title",
            "Required": true,
            "Title": "Project",
            "__metadata": {
              "type": "SP.FieldLookup"
            }
          },
          "client_validation_formula": "__dbmlsp_unmanaged__",
          "custom_formatter": null,
          "display_title": "Project",
          "lookup_creation_parameters": {
            "FieldTypeKind": 7,
            "LookupFieldName": "Title",
            "Required": true,
            "Title": "Project",
            "__metadata": {
              "type": "SP.FieldCreationInformation"
            }
          },
          "seal": false,
          "target_list": "APP_Project",
          "title": "Project",
          "validation_formula": "__dbmlsp_unmanaged__",
          "validation_message": "__dbmlsp_unmanaged__"
        },
        {
          "body": {
            "Description": "Optional due date.",
            "DisplayFormat": 0,
            "FieldTypeKind": 4,
            "Title": "DueDate",
            "__metadata": {
              "type": "SP.FieldDateTime"
            }
          },
          "client_validation_formula": "__dbmlsp_unmanaged__",
          "custom_formatter": null,
          "display_title": "Due Date",
          "seal": false,
          "title": "DueDate",
          "validation_formula": "__dbmlsp_unmanaged__",
          "validation_message": "__dbmlsp_unmanaged__"
        }
      ],
      "folders": [],
      "is_library": false,
      "item_security": null,
      "kind": "List",
      "major_version_limit": 500,
      "prevent_deletion": false,
      "renamed_from": [],
      "title": "APP_Task",
      "title_patch": {
        "Description": "",
        "Required": true,
        "__metadata": {
          "type": "SP.FieldText"
        }
      },
      "validation_described": null,
      "validation_formula": null,
      "validation_hoisted": [],
      "validation_message": null
    },
    {
      "base_template": 100,
      "content_types_enabled": false,
      "description": "Parser-fixture singleton settings list, one row holding the fixture configuration. Provisioned by dbml-sharepoint from simple-test for list AppSettings.",
      "disable_attachments": false,
      "enable_minor_versions": false,
      "enable_versioning": true,
      "expected_marker": "Provisioned by dbml-sharepoint from simple-test for list AppSettings.",
      "fields_phase1": [],
      "folders": [],
      "is_library": false,
      "item_security": null,
      "kind": "List",
      "major_version_limit": 500,
      "prevent_deletion": false,
      "renamed_from": [],
      "title": "APP_AppSettings",
      "title_patch": {
        "Description": "App Settings singleton.",
        "Required": true,
        "__metadata": {
          "type": "SP.FieldText"
        }
      },
      "validation_described": null,
      "validation_formula": null,
      "validation_hoisted": [],
      "validation_message": null
    }
  ],
  "permission_levels": [
    {
      "base_permissions": {
        "high": "0",
        "low": "2049"
      },
      "description": "Test permission level. Provisioned by dbml-sharepoint from simple-test for level Schema Manager.",
      "expected_marker": "Provisioned by dbml-sharepoint from simple-test for level Schema Manager.",
      "name": "Schema Manager",
      "previous_names": []
    }
  ],
  "phase2_lookups": [],
  "requires_manage_permissions": true,
  "seed_items": [],
  "views": [
    {
      "adopts_builtin_view": false,
      "aggregations": "",
      "caml_query": "\u003cWhere\u003e\u003cAnd\u003e\u003cOr\u003e\u003cIsNull\u003e\u003cFieldRef Name=\"Status\"/\u003e\u003c/IsNull\u003e\u003cNeq\u003e\u003cFieldRef Name=\"Status\"/\u003e\u003cValue Type=\"Text\"\u003eClosed\u003c/Value\u003e\u003c/Neq\u003e\u003c/Or\u003e\u003cOr\u003e\u003cIsNotNull\u003e\u003cFieldRef Name=\"ID\"/\u003e\u003c/IsNotNull\u003e\u003cIsNull\u003e\u003cFieldRef Name=\"ID\"/\u003e\u003c/IsNull\u003e\u003c/Or\u003e\u003c/And\u003e\u003c/Where\u003e\u003cOrderBy\u003e\u003cFieldRef Name=\"SortOrder\"/\u003e\u003c/OrderBy\u003e",
      "formatting": "{\"additionalRowClass\":\"=if([$Status] == \u0027Closed\u0027, \u0027sp-css-backgroundColor-BgLightGray\u0027, \u0027\u0027)\"}",
      "hidden": false,
      "list": "APP_Project",
      "renamed_from": [],
      "row_limit": 100,
      "scope": null,
      "set_default": true,
      "title": "Open projects",
      "url_slug": "OpenProjects",
      "view_fields": [
        "Title",
        "Status",
        "SortOrder"
      ],
      "widths": null
    },
    {
      "adopts_builtin_view": false,
      "aggregations": "",
      "caml_query": "",
      "formatting": null,
      "hidden": true,
      "list": "APP_Project",
      "renamed_from": [],
      "row_limit": null,
      "scope": null,
      "set_default": false,
      "title": "All Items",
      "url_slug": "AllItems",
      "view_fields": [
        "ID",
        "Title",
        "Status",
        "SortOrder",
        "Created",
        "Modified",
        "Author",
        "Editor"
      ],
      "widths": null
    },
    {
      "adopts_builtin_view": false,
      "aggregations": "",
      "caml_query": "",
      "formatting": null,
      "hidden": false,
      "list": "APP_Task",
      "renamed_from": [],
      "row_limit": null,
      "scope": null,
      "set_default": true,
      "title": "All Items",
      "url_slug": "AllItems",
      "view_fields": [
        "ID",
        "Title",
        "Project",
        "DueDate",
        "Created",
        "Modified",
        "Author",
        "Editor"
      ],
      "widths": null
    },
    {
      "adopts_builtin_view": false,
      "aggregations": "",
      "caml_query": "\u003cGroupBy Collapse=\"FALSE\"\u003e\u003cFieldRef Name=\"Project\"/\u003e\u003c/GroupBy\u003e\u003cWhere\u003e\u003cAnd\u003e\u003cLeq\u003e\u003cFieldRef Name=\"DueDate\"/\u003e\u003cValue Type=\"DateTime\"\u003e\u003cToday OffsetDays=\"30\"/\u003e\u003c/Value\u003e\u003c/Leq\u003e\u003cOr\u003e\u003cIsNotNull\u003e\u003cFieldRef Name=\"ID\"/\u003e\u003c/IsNotNull\u003e\u003cIsNull\u003e\u003cFieldRef Name=\"ID\"/\u003e\u003c/IsNull\u003e\u003c/Or\u003e\u003c/And\u003e\u003c/Where\u003e\u003cOrderBy\u003e\u003cFieldRef Name=\"DueDate\"/\u003e\u003c/OrderBy\u003e",
      "formatting": null,
      "hidden": false,
      "list": "APP_Task",
      "renamed_from": [],
      "row_limit": null,
      "scope": null,
      "set_default": false,
      "title": "Due soon",
      "url_slug": "DueSoon",
      "view_fields": [
        "Title",
        "Project",
        "DueDate"
      ],
      "widths": null
    },
    {
      "adopts_builtin_view": false,
      "aggregations": "",
      "caml_query": "",
      "formatting": null,
      "hidden": false,
      "list": "APP_AppSettings",
      "renamed_from": [],
      "row_limit": null,
      "scope": null,
      "set_default": true,
      "title": "All Items",
      "url_slug": "AllItems",
      "view_fields": [
        "ID",
        "Title",
        "Created",
        "Modified",
        "Author",
        "Editor"
      ],
      "widths": null
    }
  ]
};

  const TYPE_AS_STRING_BY_KIND = new Map([[2, "Text"], [3, "Note"], [4, "DateTime"], [6, "Choice"], [7, "Lookup"], [8, "Boolean"], [9, "Number"], [11, "URL"], [15, "MultiChoice"], [17, "Calculated"], [20, "User"]]);
  const MULTI_TYPE_AS_STRING_BY_KIND = new Map([[7, "LookupMulti"]]);
  const BASE_TYPE_AS_STRING = new Map([["LookupMulti", "Lookup"]]);
