"""Editable content blocks for the SharkSpin web experience."""

DASHBOARD_FACTS = [
    {
        "id": "main-spin",
        "title": "Main Spin Cab",
        "body": "Pull the chrome lever to consume energy, roll three reels, and earn SharkCoins, Energy bursts, or Wheel Tokens depending on the neon icons you line up.",
        "icon": "/static/images/info-spins.svg",
    },
    {
        "id": "daily",
        "title": "Daily Rewards",
        "body": "Claim your captain's log-in bonus every 24 hours. Streak milestones drop bonus Wheel Tokens and scale the coin/energy yield automatically.",
        "icon": "/static/images/info-daily.svg",
    },
    {
        "id": "wheel",
        "title": "Wheel of Tides",
        "body": "Spend Wheel Tokens or free charges to spin the animated tide wheel. Rewards range from burst energy to premium sticker packs.",
        "icon": "/static/images/info-wheel.svg",
    },
    {
        "id": "albums",
        "title": "Sticker Albums",
        "body": "Open packs with SharkCoins, fill themed albums, and claim completion bonuses that deliver Wheel Tokens and energy refills.",
        "icon": "/static/images/info-album.svg",
    },
    {
        "id": "shop",
        "title": "Star Shop",
        "body": "Purchase curated Star bundles from inside the mini app. Each pack lists Stars cost, energy payload, and bonus Wheel Token drops.",
        "icon": "/static/images/info-starshop.svg",
    },
    {
        "id": "events",
        "title": "Live Events",
        "body": "Seasonal regattas and pop-up tournaments appear here with progress meters, group goals, and time-limited payouts.",
        "icon": "/static/images/info-guide.svg",
    },
]

GUIDE_SECTIONS = [
    {
        "title": "Main Spin Mechanics",
        "entries": [
            {
                "heading": "Energy Cost",
                "description": "Each pull costs 1⚡ per multiplier tier. Win backs energy with ⚡ symbols on the reels or via daily rewards.",
            },
            {
                "heading": "Reward Symbols",
                "description": "🪙 adds SharkCoins, ⚡ refunds energy, and 🌀 grants Wheel Tokens. Special icons amplify based on double or triple matches.",
            },
            {
                "heading": "Multipliers",
                "description": "Tap a multiplier chip before spinning to wager additional energy for proportionally larger rewards.",
            },
        ],
    },
    {
        "title": "Progress & Levels",
        "entries": [
            {
                "heading": "XP Tracking",
                "description": "SharkCoins earned feed directly into level XP. The progress bar shows current tier, next threshold, and remaining XP.",
            },
            {
                "heading": "Level Rewards",
                "description": "Configure level-up bonuses in Config.LEVEL_REWARDS to automatically grant coins, energy, or unique items when players level up.",
            },
        ],
    },
    {
        "title": "Daily Flow",
        "entries": [
            {
                "heading": "Claim Window",
                "description": "Rewards refresh every 24 hours. Missing more than 48 hours resets the streak counter.",
            },
            {
                "heading": "Milestones",
                "description": "Edit Config.DAILY_MILESTONES to choose which streak days award bonus Wheel Tokens.",
            },
        ],
    },
    {
        "title": "Shop Administration",
        "entries": [
            {
                "heading": "Star Packs",
                "description": "Update Config.STAR_PACKAGES to change pricing, energy values, descriptions, or artwork for each bundle.",
            },
            {
                "heading": "Invoice Links",
                "description": "Provide TELEGRAM_BOT_TOKEN and BOT_USERNAME environment variables so the mini app can generate in-app purchase invoices.",
            },
        ],
    },
    {
        "title": "Wheel of Tides",
        "entries": [
            {
                "heading": "Rewards",
                "description": "Adjust WheelReward rows in the database or extend ensure_default_wheel_rewards for new prize colors and amounts.",
            },
            {
                "heading": "Token Costs",
                "description": "Tune Config.WHEEL_TOKEN_COST and Config.DAILY_FREE_WHEEL_SPINS to rebalance free vs. paid spins.",
            },
        ],
    },
    {
        "title": "Sticker Albums",
        "entries": [
            {
                "heading": "Album Catalog",
                "description": "Maintain sticker albums through the database or ensure_default_albums helper. Each album exposes description, cost, and rewards.",
            },
            {
                "heading": "Pack Pricing",
                "description": "Modify StickerAlbum.sticker_cost or update Config constants to influence coin sinks.",
            },
        ],
    },
]

TASKBAR_LINKS = [
    {"target": "main", "label": "Main Spin", "emoji": "🎰"},
    {"target": "wheel", "label": "Wheel of Tides", "emoji": "🌀"},
    {"target": "albums", "label": "Albums", "emoji": "📔"},
    {"target": "shop", "label": "Shop", "emoji": "⭐"},
    {"target": "help", "label": "Help", "emoji": "❓"},
]
