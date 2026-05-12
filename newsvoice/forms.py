from django import forms


class NewsSearchForm(forms.Form):
    CATEGORY_CHOICES = [
        ("general", "総合"),
        ("economy", "経済"),
        ("ai", "AI"),
        ("semiconductor", "半導体"),
        ("stock_market", "株式市場"),
    ]
    MAX_RECORD_CHOICES = [(5, "5件"), (10, "10件"), (20, "20件")]
    TIMESPAN_CHOICES = [
        ("1d", "1日"),
        ("3d", "3日"),
        ("7d", "7日"),
    ]
    LANGUAGE_CHOICES = [
        ("", "指定なし"),
        ("japanese", "日本語"),
        ("english", "英語"),
        ("chinese", "中国語"),
        ("korean", "韓国語"),
        ("french", "フランス語"),
        ("german", "ドイツ語"),
        ("spanish", "スペイン語"),
    ]

    category = forms.ChoiceField(label="カテゴリ", choices=CATEGORY_CHOICES, required=False)
    keyword = forms.CharField(label="キーワード", max_length=255, required=False)
    max_records = forms.ChoiceField(label="取得件数", choices=MAX_RECORD_CHOICES, initial=5)
    timespan = forms.ChoiceField(label="対象期間", choices=TIMESPAN_CHOICES, initial="1d")
    language = forms.ChoiceField(label="言語", choices=LANGUAGE_CHOICES, required=False, initial="")
