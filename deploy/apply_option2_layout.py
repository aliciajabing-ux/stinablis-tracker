#!/usr/bin/env python3
# WHAT THIS FILE DOES: Gives the Materials page the "Option 2" row layout (spacing and grouping only): wider Name box,
#   name in bold with the supplier under it, spool chip + "Mark Dried Today" side by side, printer settings under a faint
#   dashed line, "950 g" never splits. It only adds one block of style rules and wraps the material name in one <span>.
#   It does NOT touch any button, form, link, route or the spool-care code. Backs up the file first; stops without
#   changes if the page is not the one it expects; safe to run twice.
# WHO CAN USE IT: Developers. Run inside /home/stinablisdemo/stinablis_new_preview:  python3 apply_option2_layout.py
import os, shutil, sys, time

TEMPLATE = os.path.join(os.getcwd(), "app", "templates", "materials_list.html")
MARK = "OPTION 2 LAYOUT"
NAME_OLD = '<td data-label="Name">{{ material.name }}'
NAME_NEW = '<td data-label="Name"><span class="m-name">{{ material.name }}</span>'
KEEP = ["Open Spool Today", "Mark Dried Today", "settings-line", "material.care", "spool_action", "csrf_token", "row-actions", "640px"]

CSS = """  /* OPTION 2 LAYOUT (2026-11-26): spacing and grouping only. Group 1 name + supplier, group 2 spool care, group 3 printer settings. */
  .table-wrap .m-name { display: block; font-size: 1.1rem; font-weight: 600; line-height: 1.3; }
  .table-wrap .m-name + .memo { margin-top: 3px; }
  .table-wrap .spool { margin-top: 12px; gap: 10px; align-items: center; }
  .table-wrap .settings-line { margin-top: 10px; padding-top: 10px; border-top: 1px dashed var(--line, #3a3933); border-radius: 0; font-size: 0.8rem; line-height: 1.5; }
  .table-wrap td[data-label="Left"] { white-space: nowrap; }
  @media (min-width: 641px) {
    .table-wrap td[data-label="Name"] { width: 42%; }
    .table-wrap .spool .btn.small { min-height: 36px; padding: 6px 12px; font-size: 0.85rem; }
    .table-wrap td { vertical-align: middle; padding-top: 16px; padding-bottom: 16px; }
  }
  @media (max-width: 640px) {
    .table-wrap td[data-label="Name"] { padding-bottom: 8px !important; }
    .table-wrap .spool .btn.small { min-height: 44px; }
  }
"""


# Stops with a plain message and changes nothing.
def stop(message):
    print("\nSTOPPED, NOTHING WAS CHANGED:", message)
    sys.exit(1)


if not os.path.exists(TEMPLATE):
    stop("cannot find " + TEMPLATE + " (run this inside /home/stinablisdemo/stinablis_new_preview)")
with open(TEMPLATE, encoding="utf-8") as handle:
    old = handle.read()
if MARK in old:
    print("Already applied. Nothing to do.")
    sys.exit(0)
if old.count(NAME_OLD) != 1 or old.count("</style>") != 1:
    stop("this is not the page I expect (name cell found %d times, </style> found %d times)" % (old.count(NAME_OLD), old.count("</style>")))
new = old.replace(NAME_OLD, NAME_NEW).replace("</style>", CSS + "</style>")
try:
    import jinja2
    jinja2.Environment().parse(new)
except ImportError:
    print("(jinja2 not importable here; page syntax not pre-checked)")
for word in KEEP:
    if new.count(word) < old.count(word):
        stop("'%s' would disappear" % word)
backup = TEMPLATE + ".before_option2_" + time.strftime("%Y%m%d-%H%M%S")
shutil.copy2(TEMPLATE, backup)
with open(TEMPLATE, "w", encoding="utf-8", newline="\n") as handle:
    handle.write(new)
print("Backup:", backup)
print("Kept (before -> after):", {w: (old.count(w), new.count(w)) for w in KEEP})
print("\nALL GOOD. Now click Reload on the Web tab.")
