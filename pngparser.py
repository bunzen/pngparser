#!/usr/bin/env python
"""
Copyright (c) 2015, Geir Skjotskift <geir@underworld.no>

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH
REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND
FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT,
INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM
LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR
OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
PERFORMANCE OF THIS SOFTWARE.
"""

import argparse
import struct
import binascii
import zlib
import hashlib
import os

PNGMAGIC = "\x89\x50\x4e\x47\x0d\x0a\x1a\x0a"

args = None   # used to store command line arguments.

class PNGFile(object):

    def __init__(self, data):
        if not is_png(data):
            raise ParseError("Error parsing PNG data. Missing magic header")
        self.size = len(data)
        self.data = data

    def __str__(self):
        return "{0:,} byte PNG file".format(self.size)

    @property
    def chunks(self):
        offset = len(PNGMAGIC)
        while offset < len(self.data):
            chunk_start = offset
            chunk_size = struct.unpack(">I", self.data[offset:offset+4])[0]
            offset += 4
            chunk_type = struct.unpack(">4s", self.data[offset:offset+4])[0]
            offset += 4
            chunk_data = self.data[offset:offset+chunk_size]
            offset += chunk_size
            chunk_crc32 = struct.unpack(">i", self.data[offset:offset+4])[0]
            offset += 4
            yield PNGChunk(chunk_start, chunk_type, chunk_data, chunk_crc32)


class PNGChunk(object):

    def __init__(self, offset, chunk_type, data, crc32):
        self.type = chunk_type
        self.offset = offset
        self.data = data
        self.crc32 = crc32
        self.valid = binascii.crc32(self.type + self.data) == crc32
        self.term_color = False

    def __str__(self):
        crc = "{0:08X}".format(struct.unpack("I", struct.pack("i", self.crc32))[0])
        crc_nocolor = crc
        mytype = self.type
        if self.term_color:
            crc = bcolor.OKGREEN + crc + bcolor.ENDC
            mytype = bcolor.OKBLUE + mytype + bcolor.ENDC
        chunk_size = "{0:#04x}".format(len(self.data) + 12)
        if self.valid:
            return "PNGChunk (type: {0} at offset {1:#08x}, size {3} (CRC32:{2})".format(
                mytype,
                self.offset,
                crc,
                chunk_size)

        msg = "CRC32 ERROR # PNGChunk (type: {0} at offset {1:#08x}, size {3} (CRC32:{2})".format(
            self.type,
            self.offset,
            crc_nocolor,
            chunk_size)
        if self.term_color:
            return bcolor.FAIL + msg + bcolor.ENDC
        return msg




class ParseError(Exception):

    def __init__(self, value):
        Exception.__init__(self, value)
        self.value = value

    def __str__(self):
        return repr(self.value)


class bcolor(object):

    def __init__(self):
        pass

    HEADER = '\033[95m'
    OKBLUE = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class Parser(object):

    color = False
    verbose = False
    _dumpdir = None
    data = ""
    type = "UNKNOWN"

    def __init__(self, value, offset):
        self.type = value
        self.offset = offset

    def __str__(self):
        return "{0} parser object".format(self.type)

    @property
    def dumpdir(self):
        return self._dumpdir

    @dumpdir.setter
    def dumpdir(self, val):
        self._dumpdir = val
        if not self.data:
            return
        if self._dumpdir:
            fname = "{0}_{1:08x}_{2}.dat".format(
                hashlib.md5(self.data).hexdigest(),
                self.offset,
                self.type)
            fname = os.path.join(self.dumpdir, fname)
            with open(fname, "wb") as hdata:
                hdata.write(self.data)


class IHDR(Parser):

    def __init__(self, _, chunk):
        Parser.__init__(self, "IHDR", chunk.offset)
        data = chunk.data
        self.width = struct.unpack(">I", data[0:4])[0]
        self.height = struct.unpack(">I", data[4:8])[0]
        self.bit_depth = struct.unpack(">B", data[8])[0]
        self.color_type = struct.unpack(">B", data[9])[0]
        self.compression_method = struct.unpack(">B", data[10])[0]
        self.filter_method = struct.unpack(">B", data[11])[0]
        self.interlace_method = struct.unpack(">B", data[12])[0]

    def __str__(self):
        if self.color:
            msg = "General Info: {3}{0}x{1}{4} {2}bit image\n".format(
                self.width,
                self.height,
                self.bit_depth,
                bcolor.OKBLUE, bcolor.ENDC)
        else:
            msg = "General Info: {0}x{1} {2}bit image\n".format(self.width, self.height, self.bit_depth)
        color_type_txt = "Color Type: "
        if self.color_type == 0:
            color_type_txt += "Greyscale"
        elif self.color_type == 2:
            color_type_txt += "RGB"
        elif self.color_type == 3:
            color_type_txt += "Palette Index"
        elif self.color_type == 4:
            color_type_txt += "Greyscale + alpha sample"
        elif self.color_type == 6:
            color_type_txt += "RGB + alpha sample"
        msg += color_type_txt + "\n"
        msg += "Compression Method: " + str(self.compression_method) + "\n"
        msg += "Filter Method: " + str(self.filter_method) + "\n"
        msg += "Interlace Method: " + str(self.interlace_method)
        return msg


class sRGB(Parser):

    def __init__(self, ihdr, chunk):
        Parser.__init__(self, "sRGB", chunk.offset)
        self.ihdr = ihdr
        data = chunk.data
        self.intent = struct.unpack(">B", data[0])[0]

    def __str__(self):

        if self.intent == 0:
            return "Intent: Perceptual"
        elif self.intent == 1:
            return "Intent: Relative colorimetric"
        elif self.intent == 2:
            return "Intent: Saturation"
        elif self.intent == 3:
            return "Intent: Absolute colorimetric"
        if self.color:
            return bcolor.FAIL + "Intent: UNKNOWN" + bcolor.ENDC
        return "Intent: UNKNOWN"


class bKGD(Parser):

    def __init__(self, ihdr, chunk):
        Parser.__init__(self, "bKGD", chunk.offset)
        data = chunk.data
        self.ihdr = ihdr
        if ihdr is None:
            raise ParseError("IHDR is not set")
        if ihdr.color_type == 3:
            self.value = struct.unpack(">B", data[0])[0]
            self.vtype = "Palette Index"
        elif ihdr.color_type == 0 or ihdr.color_type == 4:
            self.value = struct.unpack(">H", data[0:2])[0]
            self.vtype = "Grayscale"
        elif ihdr.color_type == 2 or ihdr.color_type == 6:
            self.value = struct.unpack(">HHH", data[0:6])
            self.vtype = "RGB tripplet"
        else:
            self.value = None
            self.vtype = "UNKNOWN"

    def __str__(self):
        if self.color:
            msg = "Background Color: " + bcolor.OKBLUE + str(self.value) + bcolor.ENDC + "\n"
        else:
            msg = "Background Color: " + str(self.value) + "\n"
        msg += "Value Type: " + self.vtype
        return msg


class pHYs(Parser):

    def __init__(self, ihdr, chunk):
        Parser.__init__(self, 'pHYs', chunk.offset)
        data = chunk.data
        self.ihdr = ihdr
        self.ppux = struct.unpack(">I", data[0:4])[0]
        self.ppuy = struct.unpack(">I", data[4:8])[0]
        self.unit = struct.unpack(">B", data[8])[0]

    def __str__(self):
        unit = "cm" if self.unit == 1 else "unknown unit"
        try:
            dimx = (self.ihdr.width / float(self.ppux))*100
            dimy = (self.ihdr.height / float(self.ppuy))*100
        except ZeroDivisionError:
            dimx = 0
            dimy = 0
        return "Physical Size: {0:.1f} x {1:.1f} {2}".format(
            dimx,
            dimy,
            unit)


class tIME(Parser):

    def __init__(self, _, chunk):
        Parser.__init__(self, "tIME", chunk.offset)
        data = chunk.data
        self.year = struct.unpack(">H", data[0:2])[0]
        self.month = struct.unpack(">B", data[2])[0]
        self.day = struct.unpack(">B", data[3])[0]
        self.hour = struct.unpack(">B", data[4])[0]
        self.minute = struct.unpack(">B", data[5])[0]
        self.second = struct.unpack(">B", data[6])[0]

    def __str__(self):
        return "Last Modified: {0}/{1}/{2} {3}:{4}.{5}".format(
            self.year,
            self.month,
            self.day,
            self.hour,
            self.minute,
            self.second)


class iCCP(Parser):

    def __init__(self, _, chunk):
        Parser.__init__(self, "iCCP", chunk.offset)
        data = chunk.data
        self.profile_name = ""
        offset = 0
        while True:
            if ord(data[offset]) == 0x00:
                offset += 1
                break
            self.profile_name += data[offset]
            offset += 1
        offset += 1
        self.compression_method = struct.unpack(">B", data[offset])[0]
        offset += 1
        self.compressed_profile = data[offset:]
        if self.compression_method == 0:
            self.compressed_profile = zlib.decompress(self.compressed_profile)

    def __str__(self):
        msg = "ICC Profile Name: {0}\n".format(self.profile_name)
        msg += "Compression Method: {0}".format(self.compression_method)
        return msg


class tEXt(Parser):

    def __init__(self, _, chunk):
        Parser.__init__(self, "tEXt", chunk.offset)
        data = chunk.data
        self.keyword = ""
        offset = 0
        while True:
            if ord(data[offset]) == 0x00:
                offset += 1
                break
            self.keyword += data[offset]
            offset += 1
        self.data = data[offset:]

    def __str__(self):
        msg = "Keyword: {0}\n".format(self.keyword)
        if self.verbose:
            msg += "Text: {0}".format(self.data)
        else:
            if len(self.data) < 1024:
                msg += "Text: {0}".format(self.data)
            else:
                msg += "Text: {0} ...[snip]".format(self.data[:1024])
        return msg


class zTXt(Parser):

    def __init__(self, _, chunk):
        Parser.__init__(self, "zTXt", chunk.offset)
        data = chunk.data
        self.keyword = ""
        offset = 0
        while True:
            if ord(data[offset]) == 0x00:
                offset += 1
                break
            self.keyword += data[offset]
            offset += 1
        offset += 1
        self.data = zlib.decompress(data[offset:])

    def __str__(self):
        msg = "Keyword: {0}\n".format(self.keyword)
        if self.verbose:
            msg += "Text: {0}".format(self.data)
        else:
            if len(self.data) < 1024:
                msg += "Text: {0}".format(self.data)
            else:
                msg += "Text: {0} ...[snip]".format(self.data[:1024])
        return msg


class iTXt(Parser):

    def __init__(self, _, chunk):
        Parser.__init__(self, "iTXt", chunk.offset)
        data = chunk.data
        self.keyword = ""
        offset = 0
        while True:
            if ord(data[offset]) == 0x00:
                offset += 1
                break
            self.keyword += data[offset]
            offset += 1
        self.compression_flag = struct.unpack(">B", data[offset])[0] == 1
        offset += 1
        self.compression_method = struct.unpack(">B", data[offset])[0]
        offset += 1
        self.language_tag = ""
        while True:
            if ord(data[offset]) == 0x00:
                offset += 1
                break
            self.language_tag += data[offset]
            offset += 1
        self.translate_keyword = ""
        while True:
            if ord(data[offset]) == 0x00:
                offset += 1
                break
            self.translate_keyword += data[offset]
            offset += 1
        self.data = data[offset:]
        if self.compression_flag and self.compression_method == 0:
            self.data = zlib.decompress(self.data)

    def __str__(self):
        if self.color:
            msg = "Keyword: {1}{0}{2}\n".format(self.keyword, bcolor.OKBLUE, bcolor.ENDC)
        else:
            msg = "Keyword: {0}\n".format(self.keyword)
        msg += "Compressed: {0}\n".format(self.compression_flag)
        msg += "Compression Method: {0}\n".format(self.compression_method)
        msg += "Language Tag: {0}\n".format(self.language_tag)
        msg += "Translated Keyword: {0}\n".format(self.translate_keyword)
        if self.verbose:
            msg += "Text: {0}".format(self.data)
        else:
            if len(self.data) < 1024:
                msg += "Text: {0}".format(self.data)
            else:
                if self.color:
                    msg += "Text: {0} {1}...[snip]{2}".format(self.data[:1024], bcolor.WARNING, bcolor.ENDC)
                else:
                    msg += "Text: {0} ...[snip]".format(self.data[:1024])
        return msg


class pCAL(Parser):

    def __init__(self, _, chunk):
        Parser.__init__(self, "pCAL", chunk.offset)
        data = chunk.data
        self.calibration_name = ""
        offset = 0
        while True:
            if ord(data[offset]) == 0x00:
                offset += 1
                break
            self.calibration_name += data[offset]
            offset += 1
        self.x0 = struct.unpack(">I", data[offset:offset+4])[0]
        offset += 4
        self.x1 = struct.unpack(">I", data[offset:offset+4])[0]
        offset += 4
        self.eqtype = struct.unpack(">B", data[offset])[0]
        offset += 1
        self.num_params = struct.unpack(">B", data[offset])[0]
        offset += 1
        self.unit_name = ""
        while True:
            if ord(data[offset]) == 0x00:
                offset += 1
                break
            self.unit_name += data[offset]
            offset += 1
        self.p0 = ""
        while True:
            if ord(data[offset]) == 0x00:
                offset += 1
                break
            self.p0 += data[offset]
            offset += 1
        self.pl = data[offset:]

    def __str__(self):
        msg = "Pixel Calibration"
        msg += "Calibration Name: {0}\n".format(self.calibration_name)
        msg += "x0: {0}\nx1: {1}\nEquation Type: {2}\n".format(self.x0, self.x1, self.eqtype)
        msg += "Number of parameters: {0}\n".format(self.num_params)
        msg += "Unit Name: {0}\n".format(self.unit_name)
        msg += "Parameter 0: {0}\n".format(self.p0)
        msg += "Parameter L: {0}".format(self.pl)
        return msg


class cHRM(Parser):

    def __init__(self, _, chunk):
        Parser.__init__(self, "cHRM", chunk.offset)
        data = chunk.data
        self.wpx = struct.unpack(">I", data[0:4])[0] / 100000.
        self.wpy = struct.unpack(">I", data[4:8])[0] / 100000.
        self.redx = struct.unpack(">I", data[8:12])[0] / 100000.
        self.redy = struct.unpack(">I", data[12:16])[0] / 100000.
        self.greenx = struct.unpack(">I", data[16:20])[0] / 100000.
        self.greeny = struct.unpack(">I", data[20:24])[0] / 100000.
        self.bluex = struct.unpack(">I", data[24:28])[0] / 100000.
        self.bluey = struct.unpack(">I", data[28:32])[0] / 100000.

    def __str__(self):
        msg = "Primary chromaticities and white point\n"
        msg += "White Point x: {0}\n".format(self.wpx)
        msg += "White Point y: {0}\n".format(self.wpy)
        msg += "Red x: {0}\n".format(self.redx)
        msg += "Red y: {0}\n".format(self.redy)
        msg += "Green x: {0}\n".format(self.bluex)
        msg += "Green y: {0}\n".format(self.bluey)
        msg += "Blue x: {0}\n".format(self.greenx)
        msg += "Blue y: {0}".format(self.greeny)
        return msg


class gAMA(Parser):

    def __init__(self, _, chunk):
        Parser.__init__(self, "gAMA", chunk.offset)
        data = chunk.data
        self.gamma = struct.unpack(">I", data[:4])[0] / 100000.

    def __str__(self):
        return "Gamma: {0:.2f}".format(self.gamma)

chunk_parser = {
    "IHDR": IHDR,
    "sRGB": sRGB,
    "bKGD": bKGD,
    "pHYs": pHYs,
    "tIME": tIME,
    "iCCP": iCCP,
    "tEXt": tEXt,
    "zTXt": zTXt,
    "iTXt": iTXt,
    "pCAL": pCAL,
    "cHRM": cHRM,
    "gAMA": gAMA,
}


def is_png(data):
    return data.startswith(PNGMAGIC)


def parse_arguments():
    """Parse command line arguments, storing them in global args var"""
    parser = argparse.ArgumentParser(description='PNG file parser. copyright (c) 2015, Geir Skjotskift <geir@underworld.no>')
    parser.add_argument('filename', metavar='FILENAME', type=str, nargs='+',
                        help='the name of the png-file to parse')
    parser.add_argument('--verbose', help='more verbose output', action='store_true')
    parser.add_argument('--color', help='colorize  output', action='store_true')
    parser.add_argument('-D', '--dumpdir', metavar="DIR", type=str, help="Some meta fields may be written to file in this directory")

    global args
    args = parser.parse_args()


if __name__ == "__main__":
    parse_arguments()
    for f in args.filename:
        try:
            png = PNGFile(open(f).read())
            print "#"
            _ihdr = None
            for _chunk in png.chunks:
                if _chunk.type == "IHDR":
                    _ihdr = IHDR(None, _chunk)
                _chunk.term_color = args.color
                _parser = chunk_parser.get(_chunk.type, None)
                if args.verbose:
                    print _chunk
                    if _parser:
                        p = _parser(_ihdr, _chunk)
                        p.color = args.color
                        p.verbose = args.verbose
                        p.dumpdir = args.dumpdir
                        print p
                        print "--------------------"
                else:
                    if _chunk.type != "IDAT" or not _chunk.valid:
                        print _chunk
                        if _parser:
                            p = _parser(_ihdr, _chunk)
                            p.color = args.color
                            p.verbose = args.verbose
                            p.dumpdir = args.dumpdir
                            print p
                            print "--------------------"
                if _chunk.type == "IEND" and _chunk.offset + 12 < len(png.data):
                    if args.color:
                        print bcolor.FAIL + "WARNING: Data past IEND block" + bcolor.ENDC
                    else:
                        print "WARNING: Data past IEND block"

            print png, f, "containing", len(list(png.chunks)), "chunks."
        except ParseError as e:
            print str(e), f
