import re

from io import BytesIO
from time import sleep

from livestreamer.exceptions import PluginError
from livestreamer.packages.flashmedia import AMFPacket, AMFMessage
from livestreamer.packages.flashmedia.types import AMF3ObjectBase
from livestreamer.plugin import Plugin
from livestreamer.plugin.api import http, validate
from livestreamer.stream import HLSStream, HTTPStream


REQUEST_KEY = "BCpkADawqM0EK2RNHjuaccclw9UloSZlamA8vmU4ZKtXm4pE6zs-vNcNWLpyEznFMEQjZlxNs9EkrXQfOPJpcTUwBOACs3aMJMG2rPnWFv_H_LlQyUtU5OC7tTxrlCjqzbrvBRkm7RIhN_8J"
STREAM_NAMES = ["270p", "360p", "480p", "720p", "source"]
STREAM_RATE = ["250", "500", "1000", "2400", "3300"]

HEADERS = {
    'Accept': 'application/json;pk=BCpkADawqM0EK2RNHjuaccclw9UloSZlamA8vmU4ZKtXm4pE6zs-vNcNWLpyEznFMEQjZlxNs9EkrXQfOPJpcTUwBOACs3aMJMG2rPnWFv_H_LlQyUtU5OC7tTxrlCjqzbrvBRkm7RIhN_8J'
}

_url_re = re.compile("http(s)?://(\w+\.)?azubu.uol.com.br/(?P<domain>\w+)")
CHANNEL_INFO_URL = "http://api.azubu.tv/public/modules/last-video/%s/info"
CHANNEL_INFO_URL_2 = "http://embed.azubu.tv/%s?autoplay=true"
CHANNEL_INFO_URL_3 = "https://edge.api.brightcove.com/playback/v1/accounts/%s/videos/ref:%s"


class AzubuTV(Plugin):
    @classmethod
    def can_handle_url(cls, url):
        return _url_re.match(url)

    @classmethod
    def stream_weight(cls, stream):
        if stream == "source":
            weight = 1080
        else:
            weight, group = Plugin.stream_weight(stream)

        return weight, "azububr"
            
    def _get_player_params(self, retries=5):
        match = _url_re.match(self.url)
        domain = match.group('domain')
        try:
            res = http.get(CHANNEL_INFO_URL % str(domain))
        except PluginError as err:
            # The server sometimes gives us 404 for no reason
            if "404" in str(err) and retries:
                sleep(1)
                return self._get_player_params(retries - 1)
            else:
                raise
        channel_info = http.json(res)
        channel_info = channel_info['data']

        reference_id = channel_info['reference_id']

        is_live = channel_info['status']
        if is_live == "ACTIVE":
            is_live = True
        else:
            is_live = False

        player_id = channel_info['id']

        return reference_id, player_id, is_live

    def _get_player_params2(self, reference, retries=5):
        try:
            res = http.get(CHANNEL_INFO_URL_2 % str(reference))
        except PluginError as err:
            # The server sometimes gives us 404 for no reason
            if "404" in str(err) and retries:
                sleep(1)
                return self._get_player_params(retries - 1)
            else:
                raise
        data = res.content
        i = data.find("data-account")
        if i == -1:
            return

        j = data.find("\"", i+15)
        acc_id = data[i+14:j]

        return acc_id

    def _get_player_params3(self, accid, reference, retries=5):
        try:
            res = http.get(CHANNEL_INFO_URL_3 % (str(accid), str(reference)), headers=HEADERS)
        except PluginError as err:
            # The server sometimes gives us 404 for no reason
            if "404" in str(err) and retries:
                sleep(1)
                return self._get_player_params(retries - 1)
            else:
                raise
        sources = http.json(res)
        sources = sources['sources']
        url = sources[0]['src']

        return url

    def _parse_result(self, res):
        res = _viewerexp_schema.validate(res)
        player = res.programmedContent["videoPlayer"]
        renditions = sorted(player.mediaDTO.renditions.values(),
                            key=lambda r: r.encodingRate or 100000000)

        streams = {}
        for stream_name, rendition in zip(STREAM_NAMES, renditions):
            stream = AkamaiHDStream(self.session, rendition.defaultURL)
            streams[stream_name] = stream

        return streams

    def _get_streams(self):
        reference_id, player_id, is_live = self._get_player_params()

        if not is_live:
            return

        acc_id = self._get_player_params2(reference_id)


        url = self._get_player_params3(acc_id, reference_id).replace("master.m3u8", "")
        
        streams = {}
        for i in range(len(STREAM_RATE)):
            _url = url + str(STREAM_RATE[i]) + "/azevinho.m3u8"
            s = HLSStream(self.session, _url)
            if s != None:
                streams[STREAM_NAMES[i]] = s
            #streams
        return streams

__plugin__ = AzubuTV
