"""Behavioral tests for MyTF1 helper logic."""


class TestValidateTF1Delivery:
    """_validate_tf1_delivery accepts only successful, non-US deliveries."""

    def test_accepts_200_fr(self):
        from app.providers.fr.mytf1 import MyTF1Provider
        assert MyTF1Provider._validate_tf1_delivery({'delivery': {'code': 200, 'country': 'FR'}})

    def test_rejects_403(self):
        from app.providers.fr.mytf1 import MyTF1Provider
        assert not MyTF1Provider._validate_tf1_delivery({'delivery': {'code': 403, 'country': 'FR'}})

    def test_rejects_us(self):
        from app.providers.fr.mytf1 import MyTF1Provider
        assert not MyTF1Provider._validate_tf1_delivery({'delivery': {'code': 200, 'country': 'US'}})

    def test_rejects_empty(self):
        from app.providers.fr.mytf1 import MyTF1Provider
        assert not MyTF1Provider._validate_tf1_delivery({})


class TestFormatStreamTitle:
    """_format_stream_title builds the [HLS|MPD] label."""

    def test_with_program(self):
        from app.providers.fr.mytf1 import MyTF1Provider
        assert MyTF1Provider._format_stream_title('hls', 'Quotidien', 'TF1') == '[HLS] Quotidien'

    def test_without_program_uses_fallback(self):
        from app.providers.fr.mytf1 import MyTF1Provider
        assert MyTF1Provider._format_stream_title('mpd', None, 'TF1') == '[MPD] TF1'
