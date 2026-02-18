import unittest

# A Python mirror of the ESP32 jsonExtract implementation to validate parsing behavior

def json_extract(src: str, key: str) -> str:
    key_quote = '"' + key + '"'
    kpos = src.find(key_quote)
    if kpos < 0:
        return ''
    colon = src.find(':', kpos + len(key_quote))
    if colon < 0:
        return ''
    p = colon + 1
    while p < len(src) and src[p] in ' \t\r\n':
        p += 1
    if p >= len(src):
        return ''
    if src[p] == '"':
        start = p + 1
        end = src.find('"', start)
        if end < 0:
            return ''
        return src[start:end]
    else:
        start = p
        end = start
        while end < len(src) and src[end] not in ',}]':
            end += 1
        # trim trailing whitespace
        last = end - 1
        while last >= start and src[last] in ' \t\r\n':
            last -= 1
        if last < start:
            return ''
        return src[start:last+1]


class TestJsonExtract(unittest.TestCase):
    def test_simple_quoted(self):
        src = '{"ssid":"myNet","password":"p@ss"}'
        self.assertEqual(json_extract(src, 'ssid'), 'myNet')
        self.assertEqual(json_extract(src, 'password'), 'p@ss')

    def test_spaced(self):
        src = '{ "ssid" : "network name" , "api_host" : "http://10.0.0.1/" }'
        self.assertEqual(json_extract(src, 'ssid'), 'network name')
        self.assertEqual(json_extract(src, 'api_host'), 'http://10.0.0.1/')

    def test_unquoted_values(self):
        src = '{"flag":true, "num": 123, "nullval": null }'
        self.assertEqual(json_extract(src, 'flag'), 'true')
        self.assertEqual(json_extract(src, 'num'), '123')
        self.assertEqual(json_extract(src, 'nullval'), 'null')

    def test_missing(self):
        src = '{"a":1}'
        self.assertEqual(json_extract(src, 'b'), '')


if __name__ == '__main__':
    unittest.main()
