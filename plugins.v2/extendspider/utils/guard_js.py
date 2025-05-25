import base64


def x(input_str, key):
    key += 'PTNo2n3Ev5'
    output = ''
    for i in range(len(input_str)):
        char_code = ord(input_str[i]) ^ ord(key[i % len(key)])
        output += chr(char_code)
    return output


def b(input_str):
    return base64.b64encode(input_str.encode()).decode()


def get_guard_ret(guard):
    parts = '2|5|6|4|1|0|7|3'.split('|')  # 实际没用到，保留以对照原结构
    guard_prefix = guard[:8]
    guard_suffix = int(guard[12:])

    temp_value = ((guard_suffix * 2) + 0x12) - 0x2
    encrypted = x(str(temp_value), guard_prefix)
    guard_encrypted = str(encrypted)
    return b(guard_encrypted)
