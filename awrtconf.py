#!/usr/bin/env python3

# Asuswrt Configs Deobfuscator by BigNerd95

from argparse import ArgumentParser, FileType
from struct import pack, unpack
from random import randint
import json
import sys


validProfiles = [B'HDR1', B'HDR2', B'N55U', B'AC55U', B'AC55']

class Object(object):
    pass

def conf2jsonFile(output_file, body_data, profile):
    string_array = str(body_data, 'ascii').split('\x00')
    jsonConf = {}
    jsonConf['PROFILE'] = profile
    jsonConf['SETTINGS'] = {}

    for string in string_array:
        if len(string) > 0 :
            keyValue = string.split('=', 1)
            if len(keyValue) == 2:
                jsonConf['SETTINGS'][keyValue[0]] = keyValue[1]

    json.dump(jsonConf, output_file, indent=4, sort_keys=True)
    output_file.close()


def jsonFile2Conf(input_file):
    try:
        jsonConf = json.load(input_file)
    except:
        print("ERROR parsing dumped configurations file! Not json format")
        sys.exit(1)
    else:
        input_file.close()
        profile = jsonConf['PROFILE']
        buff = bytearray()

        for key, value in sorted(jsonConf['SETTINGS'].items()):
            buff.extend(bytes(key, 'ascii') + B'=' + bytes(value, 'ascii') + B'\0')

        buff.extend(bytearray(1024 - len(buff) % 1024)) # align size to next KB
        return buff, profile


def deobfuscate_body(body_data, randkey):
    body_data = bytearray(body_data)
    offset = 0xFF + randkey

    for i in range(len(body_data)):
        if body_data[i] >= 0xFD: # chars equal to randkey or randkey+1 or randkey+2 lost
            body_data[i] = 0x00
        elif body_data[i] < randkey:
            body_data[i] = offset - body_data[i] - 0x0100 # recover chars with ascii < randkey 
        else:
            body_data[i] = offset - body_data[i]

    return body_data


def obfuscate_body(body_data, randkey):
    body_data = bytearray(body_data)
    offset = 0xFF + randkey

    for i in range(len(body_data)):
        if body_data[i] == 0x00: 
            body_data[i] = 0xFD + randint(0,2) # chars equal to randkey or randkey+1 or randkey+2 will be lost 
        elif body_data[i] < randkey:
            body_data[i] = offset - body_data[i] - 0x0100 # avoid overflow for chars with ascii < randkey 
        else:
            body_data[i] = offset - body_data[i]

    return body_data


def parse_header(header_data):
    if len(header_data) == 8:
        unpacked_header = unpack('<4sI', header_data)

        if unpacked_header[0] in validProfiles:
            parsedHeader = Object()
            parsedHeader.profile = str(unpacked_header[0], 'ascii')

            if parsedHeader.profile == 'HDR1':
                parsedHeader.bodylength = unpacked_header[1]
            else:
                parsedHeader.bodylength = unpacked_header[1] & 0x00FFFFFF # remove randkey to get length
                parsedHeader.randkey = unpacked_header[1] >> 24 # remove length to get randkey

            return parsedHeader
        else:
            print('ERROR! Header unknown')
            sys.exit(1)
    else:
        print('ERROR! File too short')
        sys.exit(1)


def create_header(length, profile, randkey):
    profile = bytes(profile, 'ascii')
    if profile in validProfiles:
        if profile != 'HDR1':
            length = (randkey << 24) | length # 3 byte for length, 1 byte for randkey
        return pack('<4sI', profile, length)
    else:
        print('ERROR! Header unknown')
        sys.exit(1)


def print_info(header_info, isBackup):
    print('Profile:', header_info.profile)
    print('Body length:', header_info.bodylength, 'bytes', '('+hex(header_info.bodylength)+')\n')
    if header_info.profile == 'HDR1':
        print('Plain text conf file\n')
    else:
        print('Obfuscated conf file')
        print('Randkey:', header_info.randkey, '('+hex(header_info.randkey)+')\n')
        if isBackup:
            warinig_info_loss(header_info.randkey)
    

def warinig_info_loss(randkey):
    if randkey > 4 and randkey < 14:
        print('Warining: Printable chars lost! Remake the backup.')
    print('\nLost ASCII chars: ', randkey, '(' + hex(randkey) + '),', randkey + 1, '(' + hex(randkey + 1) + '),', randkey + 2, '(' + hex(randkey + 2) + ')')
    print('\tIf you used one of these chars in your configs,')
    print('\tplease make the backup again until the randkey is higher or at least 3 value smaller.')
    print('\tRecommended randkey values: randkey <= 4 (0x04) or randkey >= 14 (0x0E).')
    print('\tBest is 0, only 2 chars lost (0x01 and 0x02).\n')


def split_file(file_data):
    return (file_data[:8], file_data[8:])

def read_file(input_file):
    file_data = input_file.read()
    input_file.close()
    return file_data

def write_file(output_file, file_data):
    output_file.write(file_data)
    output_file.close()



def conf_pack(input_file, output_file, plaintext):
    print('** Conf Pack **')
    body_data, profile = jsonFile2Conf(input_file)
    randkey = 0

    if plaintext:
        profile = 'HDR1' # force HDR1 profile if plaintext flag is set

    if profile != 'HDR1':
        randkey = 0 # randint(0,29) # static randkey 0 until asus/broadcom fixes the algorithm
        body_data = obfuscate_body(body_data, randkey)

    header_data = create_header(len(body_data), profile, randkey)
    header_info = parse_header(header_data)
    print_info(header_info, isBackup=False)
    write_file(output_file, header_data + body_data)
    print('Configurations packed successfully!')


def conf_dump(input_file, output_file):
    print('** Conf Dump **')
    file_data = read_file(input_file)
    header_data, body_data = split_file(file_data)
    header_info = parse_header(header_data)
    print_info(header_info, isBackup=True)
    
    if header_info.profile != 'HDR1':
        body_data = deobfuscate_body(body_data, header_info.randkey)

    conf2jsonFile(output_file, body_data, header_info.profile)
    print('Configurations dumped successfully!')
    

def conf_info(input_file):
    print('** Conf Info **')
    file_data = read_file(input_file)
    header_data, body_data = split_file(file_data)
    header_info = parse_header(header_data)
    print_info(header_info, isBackup=True)



def parse_cli():
    parser = ArgumentParser(description='** Asuswrt Configs Deobfuscator by BigNerd95 **')
    subparser = parser.add_subparsers(dest='subparser_name')

    infoParser = subparser.add_parser('info', help='Conf info')
    infoParser.add_argument('-i', '--input', required=True, metavar='INPUT_FILE', type=FileType('rb'))

    unsignParser = subparser.add_parser('dump', help='Conf dump')
    unsignParser.add_argument('-i', '--input', required=True, metavar='INPUT_FILE', type=FileType('rb'))
    unsignParser.add_argument('-o', '--output', required=True, metavar='OUTPUT_FILE', type=FileType('w'))

    signParser = subparser.add_parser('pack', help='Conf pack')
    signParser.add_argument('-i', '--input', required=True, metavar='INPUT_FILE', type=FileType('r'))
    signParser.add_argument('-o', '--output', required=True, metavar='OUTPUT_FILE', type=FileType('wb'))
    signParser.add_argument('-p', '--plain', required=False, action='store_true')
    
    if len(sys.argv) < 2:
        parser.print_help()

    return parser.parse_args()


def main():
    args = parse_cli()
    if args.subparser_name == 'info':
        conf_info(args.input)
    elif args.subparser_name == 'dump':
        conf_dump(args.input, args.output)
    elif args.subparser_name == 'pack':
        conf_pack(args.input, args.output, args.plain)
    
if __name__ == '__main__':
    main()
