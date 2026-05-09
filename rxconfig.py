import reflex as rx

config = rx.Config(

    app_name="PWATrial",

    plugins=[

        rx.plugins.RadixThemesPlugin(

            theme=rx.theme(
                accent_color="blue"
            )
        )
    ]
)