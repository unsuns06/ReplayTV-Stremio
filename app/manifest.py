def get_manifest():
    return {
        "id": "org.catchuptvandmore.stremio",
        "version": "1.0.0",
        "name": "Catch-up TV & More",
        "description": "French live TV and TV show replays: France 2 (Envoyé spécial, Cash Investigation, Complément d'enquête), TF1+ (Sept à huit, Quotidien), and 6play (Capital, 66 minutes, Zone Interdite, Enquête Exclusive)",
        "logo": "https://catch-up-tv-and-more.github.io/images/logo.png",
        "background": "https://catch-up-tv-and-more.github.io/images/background.jpg",
        "resources": [
            "catalog",
            "meta",
            "stream"
        ],
        "types": [
            "channel",
            "series"
        ],
        "catalogs": [
            {
                "id": "fr-live",
                "type": "channel",
                "name": "French Live TV"
            },
            {
                "id": "fr-francetv-replay",
                "type": "series",
                "name": "France 2 TV Shows: Envoyé spécial, Cash Investigation, Complément d'enquête"
            },
            {
                "id": "fr-mytf1-replay",
                "type": "series",
                "name": "TF1+ TV Shows: Sept à huit, Quotidien"
            },
            {
                "id": "fr-6play-replay",
                "type": "series",
                "name": "6play TV Shows: Capital, 66 minutes, Zone Interdite, Enquête Exclusive"
            },
            {
                "id": "ca-cbc-dragons-den",
                "type": "series",
                "name": "CBC Dragon's Den"
            }
        ],
        "idPrefixes": [
            "cutam:fr:",
            "cutam:ca:"
        ],
        "behaviorHints": {
            "configurable": True,
            "configurationRequired": False
        }
    }