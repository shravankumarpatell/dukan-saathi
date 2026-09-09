{
  "brand": {
    "product_name": "VyapaarOS (Tile ERP)",
    "personality": [
      "calm",
      "legible",
      "keyboard-first",
      "trustworthy",
      "dense-data-with-breathing-room",
      "functional-color-only"
    ],
    "anti_patterns": [
      "No Tally/Vyapar clone look (heavy borders, DOS palettes)",
      "No icon-only controls without tooltip/label",
      "No stacked modals",
      "No cluttered dashboards",
      "No decorative gradients"
    ]
  },

  "typography": {
    "google_fonts": {
      "ui_sans": {
        "name": "Manrope",
        "weights": [400, 500, 600, 700],
        "usage": "All UI text, headings, labels"
      },
      "numbers_mono": {
        "name": "IBM Plex Mono",
        "weights": [400, 500, 600],
        "usage": "Amounts, quantities, voucher numbers, table numeric columns, shortcut badges"
      }
    },
    "tailwind_notes": {
      "body_default": "text-sm md:text-base leading-6",
      "h1": "text-4xl sm:text-5xl lg:text-6xl font-semibold tracking-tight",
      "h2": "text-base md:text-lg font-medium text-muted-foreground",
      "section_title": "text-lg font-semibold",
      "table": "text-sm leading-5",
      "meta": "text-xs text-muted-foreground",
      "numbers": "[font-variant-numeric:tabular-nums] font-mono"
    },
    "content_rules": [
      "Prefer sentence case for labels and buttons.",
      "Amounts always right-aligned + tabular-nums.",
      "Show shortcut hints in tooltips and menus using <kbd>."
    ]
  },

  "color_system_oklch": {
    "notes": [
      "Functional color only: semantic states + accounting meaning (debit/credit).",
      "No purple. Use ocean-teal + ink neutrals.",
      "Tailwind v4: define tokens in index.css using @theme or :root variables; map to shadcn tokens (background/foreground/etc).",
      "Keep gradients under 20% viewport; only subtle hero/empty-state backdrops."
    ],

    "light": {
      "background": "oklch(0.985 0.004 240)",
      "foreground": "oklch(0.205 0.012 240)",
      "card": "oklch(0.995 0.002 240)",
      "card_foreground": "oklch(0.205 0.012 240)",
      "popover": "oklch(0.995 0.002 240)",
      "popover_foreground": "oklch(0.205 0.012 240)",

      "muted": "oklch(0.965 0.006 240)",
      "muted_foreground": "oklch(0.52 0.02 240)",

      "border": "oklch(0.90 0.01 240)",
      "input": "oklch(0.90 0.01 240)",

      "primary": "oklch(0.46 0.10 205)",
      "primary_foreground": "oklch(0.985 0.004 240)",

      "accent": "oklch(0.94 0.03 205)",
      "accent_foreground": "oklch(0.24 0.03 205)",

      "ring": "oklch(0.62 0.12 205)",

      "semantic": {
        "success": "oklch(0.62 0.14 155)",
        "warning": "oklch(0.74 0.14 85)",
        "danger": "oklch(0.58 0.18 25)",
        "info": "oklch(0.62 0.12 230)",

        "debit": "oklch(0.60 0.16 25)",
        "credit": "oklch(0.60 0.14 155)",

        "stock_in": "oklch(0.62 0.14 155)",
        "stock_low": "oklch(0.74 0.14 85)",
        "stock_out": "oklch(0.58 0.18 25)",

        "overdue": "oklch(0.58 0.18 25)",
        "due_soon": "oklch(0.74 0.14 85)",
        "current": "oklch(0.62 0.12 230)"
      },

      "surfaces": {
        "sidebar": "oklch(0.975 0.006 240)",
        "topbar": "oklch(0.99 0.003 240)",
        "table_header": "oklch(0.975 0.006 240)",
        "table_row_hover": "oklch(0.965 0.01 205)",
        "table_row_selected": "oklch(0.94 0.03 205)"
      }
    },

    "dark": {
      "background": "oklch(0.145 0.01 240)",
      "foreground": "oklch(0.92 0.01 240)",
      "card": "oklch(0.185 0.012 240)",
      "card_foreground": "oklch(0.92 0.01 240)",
      "popover": "oklch(0.205 0.012 240)",
      "popover_foreground": "oklch(0.92 0.01 240)",

      "muted": "oklch(0.22 0.012 240)",
      "muted_foreground": "oklch(0.72 0.015 240)",

      "border": "oklch(0.30 0.012 240)",
      "input": "oklch(0.30 0.012 240)",

      "primary": "oklch(0.72 0.11 205)",
      "primary_foreground": "oklch(0.16 0.01 240)",

      "accent": "oklch(0.26 0.03 205)",
      "accent_foreground": "oklch(0.92 0.01 240)",

      "ring": "oklch(0.78 0.12 205)",

      "semantic": {
        "success": "oklch(0.72 0.14 155)",
        "warning": "oklch(0.80 0.14 85)",
        "danger": "oklch(0.70 0.18 25)",
        "info": "oklch(0.76 0.12 230)",

        "debit": "oklch(0.70 0.18 25)",
        "credit": "oklch(0.72 0.14 155)",

        "stock_in": "oklch(0.72 0.14 155)",
        "stock_low": "oklch(0.80 0.14 85)",
        "stock_out": "oklch(0.70 0.18 25)",

        "overdue": "oklch(0.70 0.18 25)",
        "due_soon": "oklch(0.80 0.14 85)",
        "current": "oklch(0.76 0.12 230)"
      },

      "surfaces": {
        "sidebar": "oklch(0.165 0.012 240)",
        "topbar": "oklch(0.155 0.01 240)",
        "table_header": "oklch(0.175 0.012 240)",
        "table_row_hover": "oklch(0.20 0.02 205)",
        "table_row_selected": "oklch(0.24 0.03 205)"
      }
    }
  },

  "design_tokens_css_scaffold_tailwind_v4": {
    "instructions": [
      "Replace current HSL shadcn tokens in /app/frontend/src/index.css with OKLCH tokens below.",
      "Keep token names compatible with shadcn (background, foreground, card, muted, border, primary, accent, ring, destructive).",
      "Add extra semantic tokens for debit/credit/stock states.",
      "Set color-scheme for both modes."
    ],
    "index_css_snippet": "@layer base {\n  :root {\n    color-scheme: light;\n    --background: 0.985 0.004 240;\n    --foreground: 0.205 0.012 240;\n    --card: 0.995 0.002 240;\n    --card-foreground: 0.205 0.012 240;\n    --popover: 0.995 0.002 240;\n    --popover-foreground: 0.205 0.012 240;\n    --muted: 0.965 0.006 240;\n    --muted-foreground: 0.52 0.02 240;\n    --border: 0.90 0.01 240;\n    --input: 0.90 0.01 240;\n    --primary: 0.46 0.10 205;\n    --primary-foreground: 0.985 0.004 240;\n    --accent: 0.94 0.03 205;\n    --accent-foreground: 0.24 0.03 205;\n    --ring: 0.62 0.12 205;\n    --destructive: 0.58 0.18 25;\n    --destructive-foreground: 0.985 0.004 240;\n\n    /* semantic */\n    --success: 0.62 0.14 155;\n    --warning: 0.74 0.14 85;\n    --info: 0.62 0.12 230;\n    --debit: 0.60 0.16 25;\n    --credit: 0.60 0.14 155;\n    --stock-in: 0.62 0.14 155;\n    --stock-low: 0.74 0.14 85;\n    --stock-out: 0.58 0.18 25;\n\n    /* density */\n    --radius: 10px;\n    --row-h: 36px;\n    --row-h-compact: 32px;\n  }\n\n  .dark {\n    color-scheme: dark;\n    --background: 0.145 0.01 240;\n    --foreground: 0.92 0.01 240;\n    --card: 0.185 0.012 240;\n    --card-foreground: 0.92 0.01 240;\n    --popover: 0.205 0.012 240;\n    --popover-foreground: 0.92 0.01 240;\n    --muted: 0.22 0.012 240;\n    --muted-foreground: 0.72 0.015 240;\n    --border: 0.30 0.012 240;\n    --input: 0.30 0.012 240;\n    --primary: 0.72 0.11 205;\n    --primary-foreground: 0.16 0.01 240;\n    --accent: 0.26 0.03 205;\n    --accent-foreground: 0.92 0.01 240;\n    --ring: 0.78 0.12 205;\n    --destructive: 0.70 0.18 25;\n    --destructive-foreground: 0.16 0.01 240;\n\n    --success: 0.72 0.14 155;\n    --warning: 0.80 0.14 85;\n    --info: 0.76 0.12 230;\n    --debit: 0.70 0.18 25;\n    --credit: 0.72 0.14 155;\n    --stock-in: 0.72 0.14 155;\n    --stock-low: 0.80 0.14 85;\n    --stock-out: 0.70 0.18 25;\n  }\n}\n\n/* helper utilities */\n@layer utilities {\n  .bg-canvas { background-color: oklch(var(--background)); }\n  .text-ink { color: oklch(var(--foreground)); }\n  .ring-focus {\n    box-shadow: 0 0 0 2px color-mix(in oklch, oklch(var(--ring)) 35%, transparent),\n                0 0 0 5px color-mix(in oklch, oklch(var(--ring)) 18%, transparent);\n    outline: none;\n  }\n  .tabular { font-variant-numeric: tabular-nums; }\n}\n"
  },

  "layout": {
    "app_shell": {
      "structure": "Desktop-first 3-region shell: left sidebar (collapsible) + topbar + main content. Mobile: sidebar becomes Sheet.",
      "grid": {
        "desktop": "grid grid-cols-[260px_1fr]",
        "desktop_collapsed": "grid-cols-[72px_1fr]",
        "topbar_height": "h-14",
        "content_max_width": "max-w-[1600px] (center within main only, not whole app)",
        "content_padding": "px-4 sm:px-6 lg:px-8 py-6"
      },
      "sidebar": {
        "width": "w-[260px]",
        "collapsed_width": "w-[72px]",
        "sections": [
          "Company/Branch switcher",
          "Primary nav groups (Sales, Purchase, Accounting, Inventory, Parties, GST, Tools, Settings)",
          "Pinned/Recent",
          "Bottom: theme toggle + user menu"
        ],
        "nav_item": {
          "height": "h-9",
          "padding": "px-2",
          "radius": "rounded-md",
          "active_state": "bg-accent text-accent-foreground",
          "hover_state": "hover:bg-muted",
          "icon": "lucide-react size-4",
          "label": "always visible on desktop expanded; collapsed shows tooltip"
        }
      },
      "topbar": {
        "left": "Breadcrumb + page title",
        "center_optional": "Global search trigger (Cmd+K) button",
        "right": "Quick actions (New Invoice, New Voucher), notifications, help (?)",
        "rule": "One obvious primary action per screen; other actions in dropdown menu"
      }
    },

    "page_patterns": {
      "list_pages": "Top: title + filters row + primary CTA. Body: table with sticky header + sticky footer totals when needed.",
      "editor_pages": "Two-column header (party/date/series) + line-item grid + right totals panel (sticky).",
      "reports": "Left: filters (date range, branch, ledger group). Right: report table with export/print."
    }
  },

  "data_dense_tables": {
    "components": {
      "shadcn": ["table", "scroll-area", "resizable", "dropdown-menu", "popover", "command", "tooltip", "badge", "skeleton"],
      "notes": "Use shadcn Table as base; wrap in ScrollArea for sticky header + horizontal scroll. Use Resizable for column resizing."
    },
    "density": {
      "default_row_height": "h-[var(--row-h)] (36px)",
      "compact_row_height": "h-[var(--row-h-compact)] (32px)",
      "cell_padding": "px-3 py-2 (default), px-2 py-1.5 (compact)",
      "header_style": "text-xs font-semibold uppercase tracking-wide text-muted-foreground bg-[oklch(var(--muted))]",
      "borders": "Only row separators: border-b border-border/60; avoid full grid borders"
    },
    "sticky": {
      "header": "sticky top-0 z-20 backdrop-blur supports-[backdrop-filter]:bg-background/70",
      "first_column_optional": "sticky left-0 z-10 bg-background (for row identifiers)",
      "totals_footer_optional": "sticky bottom-0 z-10 bg-background/90 border-t"
    },
    "keyboard_navigation": {
      "focused_cell": "Use roving tabindex. Focused cell gets ring-focus + bg-accent/40.",
      "focused_row": "Row highlight: bg-muted/60; selected row: bg-accent.",
      "enter_behavior": "Enter commits edit and moves to next row same column; Shift+Enter moves up.",
      "arrow_keys": "Arrow keys move cell focus; Ctrl+Arrow jumps to edge.",
      "type_to_search": "In product column, typing opens Command/Combobox filtered list.",
      "escape": "Esc cancels edit and restores previous value."
    },
    "visibility_rule": "Focused row/cell must be unmistakable in both themes; do not rely on subtle border-only focus."
  },

  "forms_and_editors": {
    "voucher_entry": {
      "layout": [
        "Header strip: Voucher type, date, voucher no, branch, narration (2-col grid)",
        "Line grid: Dr/Cr rows with ledger combobox + amount + cost center + reference",
        "Right rail: totals, imbalance indicator, save actions"
      ],
      "imbalance_indicator": "If debit != credit show persistent warning banner (Alert) with semantic color; disable Save until balanced.",
      "components": ["form", "input", "select", "textarea", "table", "badge", "alert", "button", "tooltip"]
    },
    "sales_invoice_editor": {
      "layout": [
        "Top: Customer combobox + GSTIN + place of supply + invoice series/date",
        "Middle: line-item grid (product search, shade/batch, boxes/sqft, rate, discount, GST)",
        "Right sticky totals: taxable, GST split, round-off, grand total, received, balance",
        "Bottom: Save, Save & Print, More (dropdown)"
      ],
      "tile_calculator_inline": "In qty cell, allow a popover calculator: sqft -> boxes with wastage; writes back to qty.",
      "components": ["popover", "command", "table", "resizable", "separator", "card", "badge"]
    }
  },

  "command_palette_and_shortcuts": {
    "components": ["command", "dialog", "tooltip", "badge"],
    "cmdk_trigger": {
      "button": "Button variant=secondary with search icon + text 'Search' + kbd hint",
      "data_testid": "command-palette-trigger"
    },
    "palette_style": {
      "width": "w-[720px] max-w-[92vw]",
      "radius": "rounded-xl",
      "shadow": "shadow-2xl shadow-black/10 dark:shadow-black/40",
      "input": "h-11 text-sm",
      "group_heading": "text-xs text-muted-foreground px-3 py-2",
      "item": "h-10 px-3 rounded-md aria-selected:bg-accent aria-selected:text-accent-foreground",
      "kbd": "Use IBM Plex Mono, text-[11px], px-1.5 py-0.5 rounded-md bg-muted border"
    },
    "go_to_chords": {
      "pattern": "G then S (Sales), G then A (Accounting), etc.",
      "ui": "Show chord hints in sidebar tooltips and in '?' cheatsheet overlay"
    },
    "cheatsheet_overlay": {
      "component": "Dialog",
      "layout": "2-column list of shortcuts grouped by area",
      "data_testid": "shortcut-cheatsheet-dialog"
    }
  },

  "components_and_paths": {
    "primary": {
      "button": "/app/frontend/src/components/ui/button.jsx",
      "input": "/app/frontend/src/components/ui/input.jsx",
      "select": "/app/frontend/src/components/ui/select.jsx",
      "table": "/app/frontend/src/components/ui/table.jsx",
      "dialog": "/app/frontend/src/components/ui/dialog.jsx",
      "command": "/app/frontend/src/components/ui/command.jsx",
      "tooltip": "/app/frontend/src/components/ui/tooltip.jsx",
      "sheet": "/app/frontend/src/components/ui/sheet.jsx",
      "scroll_area": "/app/frontend/src/components/ui/scroll-area.jsx",
      "resizable": "/app/frontend/src/components/ui/resizable.jsx",
      "sonner": "/app/frontend/src/components/ui/sonner.jsx",
      "skeleton": "/app/frontend/src/components/ui/skeleton.jsx",
      "calendar": "/app/frontend/src/components/ui/calendar.jsx",
      "badge": "/app/frontend/src/components/ui/badge.jsx",
      "breadcrumb": "/app/frontend/src/components/ui/breadcrumb.jsx",
      "tabs": "/app/frontend/src/components/ui/tabs.jsx",
      "dropdown_menu": "/app/frontend/src/components/ui/dropdown-menu.jsx",
      "popover": "/app/frontend/src/components/ui/popover.jsx",
      "alert": "/app/frontend/src/components/ui/alert.jsx"
    },
    "composition_guidance": [
      "Prefer Dialog for modal flows; avoid stacking dialogs. Use Sheet for mobile filters/sidebar.",
      "Use Tooltip for every icon-only control; include shortcut hints.",
      "Use Badge for semantic states (Overdue, Low stock, Credit, Debit)."
    ]
  },

  "motion_and_micro_interactions": {
    "timing": "150–200ms for most UI transitions",
    "easing": "cubic-bezier(0.2, 0.8, 0.2, 1)",
    "rules": [
      "No universal transition: never transition: all.",
      "Animate opacity/background-color/box-shadow only for hover/focus.",
      "Use subtle scale (0.98) on button press.",
      "Skeletons for tables and editors; toast on every save."
    ],
    "examples": {
      "button": "transition-colors duration-150 active:scale-[0.98]",
      "row_hover": "transition-colors duration-150",
      "dialog": "use shadcn dialog animations; keep duration <= 200ms"
    }
  },

  "states": {
    "loading": {
      "pattern": "Use Skeleton rows matching table density; keep header visible.",
      "components": ["skeleton"],
      "data_testid": "loading-state"
    },
    "empty": {
      "pattern": "Centered within content area (not whole viewport): title, 1-line guidance, primary CTA, secondary link to import.",
      "visual": "Use subtle noise texture background only in empty state panel (<=20% viewport).",
      "data_testid": "empty-state"
    },
    "error": {
      "pattern": "Inline Alert at top of page + retry button; preserve user input.",
      "data_testid": "error-state"
    },
    "toast": {
      "library": "sonner",
      "rules": [
        "Toast on every save (success) and on validation errors.",
        "Include action when relevant (Undo, View invoice).",
        "Do not spam: batch repeated autosaves."
      ]
    }
  },

  "accessibility": {
    "focus": [
      "All interactive elements must have visible focus-visible ring (ring-focus utility).",
      "Never remove outline without replacement.",
      "Ensure focus order matches visual order."
    ],
    "contrast": [
      "Meet WCAG AA for text.",
      "Semantic colors must be readable on both background and muted surfaces; use badges with tinted backgrounds rather than colored text alone."
    ],
    "keyboard_first": [
      "Everything reachable via keyboard.",
      "Show shortcuts in tooltips and menus.",
      "Provide '?' overlay listing shortcuts."
    ]
  },

  "testing_attributes": {
    "rule": "All interactive and key informational elements MUST include data-testid (kebab-case).",
    "examples": [
      "data-testid=\"login-form-submit-button\"",
      "data-testid=\"sales-invoice-save-button\"",
      "data-testid=\"voucher-lineitem-ledger-combobox\"",
      "data-testid=\"table-row-0\"",
      "data-testid=\"trial-balance-export-button\""
    ]
  },

  "image_urls": {
    "textures": [
      {
        "category": "noise/texture",
        "description": "Subtle grain texture for empty states or hero-like header panels (keep under 20% viewport).",
        "url": "https://images.unsplash.com/photo-1619252584172-a83a949b6efd?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA1OTN8MHwxfHNlYXJjaHwxfHxtaW5pbWFsJTIwYWJzdHJhY3QlMjB0ZXh0dXJlJTIwZ3JhaW58ZW58MHx8fHdoaXRlfDE3ODg5NDU5MTN8MA&ixlib=rb-4.1.0&q=85"
      }
    ]
  },

  "instructions_to_main_agent": {
    "remove_default_cra_styles": [
      "Delete /app/frontend/src/App.css content or stop importing it; it contains centered CRA demo styles.",
      "Keep layout left-aligned; never apply .App { text-align:center }."
    ],
    "implementation_priorities": [
      "1) Replace index.css tokens with OKLCH tokens scaffold above (light + dark).",
      "2) Build AppShell (Sidebar + Topbar + Main) with shadcn components and lucide icons.",
      "3) Implement Command Palette using shadcn command + dialog; add Cmd/Ctrl+K listener.",
      "4) Implement table density + sticky header + keyboard focus styling utilities.",
      "5) Add data-testid to all interactive elements and key info fields."
    ],
    "libraries": {
      "cmdk": "Already implied via shadcn command; ensure cmdk is installed.",
      "framer_motion_optional": "Only if needed for subtle entrance animations; keep durations 150–200ms.",
      "recharts": "Use for dashboard sparklines only; keep charts minimal and functional."
    }
  },

  "general_ui_ux_design_guidelines_appendix": "<General UI UX Design Guidelines>\n    - You must **not** apply universal transition. Eg: `transition: all`. This results in breaking transforms. Always add transitions for specific interactive elements like button, input excluding transforms\n    - You must **not** center align the app container, ie do not add `.App { text-align: center; }` in the css file. This disrupts the human natural reading flow of text\n   - NEVER: use AI assistant Emoji characters like`🤖🧠💭💡🔮🎯📚🎭🎬🎪🎉🎊🎁🎀🎂🍰🎈🎨🎰💰💵💳🏦💎🪙💸🤑📊📈📉💹🔢🏆🥇 etc for icons. Always use **FontAwesome cdn** or **lucid-react** library already installed in the package.json\n\n **GRADIENT RESTRICTION RULE**\nNEVER use dark/saturated gradient combos (e.g., purple/pink) on any UI element.  Prohibited gradients: blue-500 to purple 600, purple 500 to pink-500, green-500 to blue-500, red to pink etc\nNEVER use dark gradients for logo, testimonial, footer etc\nNEVER let gradients cover more than 20% of the viewport.\nNEVER apply gradients to text-heavy content or reading areas.\nNEVER use gradients on small UI elements (<100px width).\nNEVER stack multiple gradient layers in the same viewport.\n\n**ENFORCEMENT RULE:**\n    • Id gradient area exceeds 20% of viewport OR affects readability, **THEN** use solid colors\n\n**How and where to use:**\n   • Section backgrounds (not content backgrounds)\n   • Hero section header content. Eg: dark to light to dark color\n   • Decorative overlays and accent elements only\n   • Hero section with 2-3 mild color\n   • Gradients creation can be done for any angle say horizontal, vertical or diagonal\n\n- For AI chat, voice application, **do not use purple color. Use color like light green, ocean blue, peach orange etc**\n\n</Font Guidelines>\n\n- Every interaction needs micro-animations - hover states, transitions, parallax effects, and entrance animations. Static = dead. \n   \n- Use 2-3x more spacing than feels comfortable. Cramped designs look cheap.\n\n- Subtle grain textures, noise overlays, custom cursors, selection states, and loading animations: separates good from extraordinary.\n   \n- Before generating UI, infer the visual style from the problem statement (palette, contrast, mood, motion) and immediately instantiate it by setting global design tokens (primary, secondary/accent, background, foreground, ring, state colors), rather than relying on any library defaults. Don't make the background dark as a default step, always understand problem first and define colors accordingly\n    Eg: - if it implies playful/energetic, choose a colorful scheme\n           - if it implies monochrome/minimal, choose a black–white/neutral scheme\n\n**Component Reuse:**\n\t- Prioritize using pre-existing components from src/components/ui when applicable\n\t- Create new components that match the style and conventions of existing components when needed\n\t- Examine existing components to understand the project's component patterns before creating new ones\n\n**IMPORTANT**: Do not use HTML based component like dropdown, calendar, toast etc. You **MUST** always use `/app/frontend/src/components/ui/ ` only as a primary components as these are modern and stylish component\n\n**Best Practices:**\n\t- Use Shadcn/UI as the primary component library for consistency and accessibility\n\t- Import path: ./components/[component-name]\n\n**Export Conventions:**\n\t- Components MUST use named exports (export const ComponentName = ...)\n\t- Pages MUST use default exports (export default function PageName() {...})\n\n**Toasts:**\n  - Use `sonner` for toasts\"\n  - Sonner component are located in `/app/src/components/ui/sonner.tsx`\n\nUse 2–4 color gradients, subtle textures/noise overlays, or CSS-based noise to avoid flat visuals.\n</General UI UX Design Guidelines>"
}
