"""
BSD Zero Clause License

Copyright (c) 2023 Brandon Irwin

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH
REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY
AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT,
INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM
LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR
OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
PERFORMANCE OF THIS SOFTWARE.
"""

import os
import sys
from ctypes import CDLL
import re
from UM.Platform import Platform
from UM.Logger import Logger
from UM.PluginRegistry import PluginRegistry
from cura.Snapshot import Snapshot
from PyQt6.QtCore import QByteArray, QIODevice, QBuffer, Qt
from cura import CuraApplication
from array import array
from enum import Enum
from ..Script import Script


this_path = os.path.dirname(os.path.abspath(__file__))


class Neptune3Model(Enum):
    disabled = 'Disabled'
    unknown = 'Unknown model'
    base = 'Base'
    pro_plus_max = 'Pro/Plus/Max'


Logger.log("d", "CreateElegooNeptune3Thumbnail plugin loading!")
# Get the class from the CreateThumbnail post processing script.


class CreateElegooNeptune3Thumbnail(Script):
    def __init__(self):
        """ Creates a thumbnail for Elegoo Neptune 3 printers. This reuses the CreateThumbnail class. """
        super().__init__()
        self.printer: Neptune3Model = Neptune3Model.unknown

    def get_selected_model(self) -> Neptune3Model:
        """ Get the selected printer model, from the GUI. """
        enabled: bool = self.getSettingValueByKey("enabled")
        model_text: str = self.getSettingValueByKey("elegoo_model").lower().strip()

        if not enabled:
            Logger.log("d", "Neptune 3 thumbnail disabled.")
            model = Neptune3Model.disabled
        elif model_text == 'base':
            model = Neptune3Model.base
        elif model_text == 'pro':
            model = Neptune3Model.pro_plus_max
        else:
            model = Neptune3Model.unknown

        Logger.log("d", "Selected printer: {}".format(model.value))
        return model

    def _convertSnapshotToGcode(self, encoded_snapshot, *args, **kwargs) -> list[str]:
        """ Get the printer type from the description. This is helpful if they based it on some other printer.
        This requires that they named their printer exactly "Elegoo Neptune 3 Pro" or whatever
        """
        model = self.get_selected_model()
        Logger.log("d", "Generating thumbnail: {}".format(model.value))
        if model == Neptune3Model.base:
            gcode = ''.join((
                n3_base_encode_image(encoded_snapshot, 100, 100, ";simage:"),
                n3_base_encode_image(encoded_snapshot, 200, 200, ";;gimage:")
            ))
        elif model == Neptune3Model.pro_plus_max:
            gcode = ''.join((
                neptune_3_pro_encode_image(encoded_snapshot, 200, 200, ";gimage:"),
                neptune_3_pro_encode_image(encoded_snapshot, 160, 160, ";simage:")
            ))
        else:
            # Unknown model
            gcode = "; CreateElegooNeptune3Thumbnail script: Skipped thumbnail generation: {}".format(model.value)

        return ["; thumbnail for Neptune 3 {}".format(model.value), gcode]

    def getSettingDataString(self) -> str:
        """ Create the settings string, which makes the scripts GUI.
        If you need to change the entries here, put them in the Neptune3Model enum, instead.
        """
        lib_filepath = get_dll_filepath()
        # True if the library files doesn't exist. This means they need to download them.
        lib_not_found = not os.path.isfile(lib_filepath)
        # True if macOS, and the file is quarantined, so won't run.
        is_quarantined = macos_check_quarantine(lib_filepath)

        if lib_not_found or is_quarantined:
            lib_dir = os.path.dirname(lib_filepath)
            lib_file = os.path.basename(lib_filepath)
            msg: list[str] = ["Additional steps required!"]

            if is_quarantined:
                # Give instructions, in the plugin, if it's quarantined.
                msg.extend([
                    "You're using macOS, and the image encoding library is under quarantine: {}".format(lib_filepath),
                    "Right click {}, click 'Open', then click the Open button.".format(lib_file)
                ])
            else:  # lib_not_found
                # Give instructions, in the plugin, if the library doesn't exist.
                os.makedirs(lib_dir, exist_ok=True)
                msg.extend([
                    "You need to get the image encoding library from Elegoo Cura, found on their website: https://www.elegoo.com/pages/3d-printing-user-support",
                    "It's the file {} in: Cura/plugins/MKS Plugin".format(lib_file),
                    "It must be placed at: {}".format(lib_filepath),
                ])
                if Platform.isOSX:
                    # Give additional instructions, for allowing execution/use.
                    msg.extend([
                        "After placing it there, right click it, then click Open, then Open, to remove it from quarantine."
                    ])

            msg.append("Then restart Cura!")
            # split up into lines

            settings_text = make_checkbox_message('\n'.join(msg))

        else:
            settings_text = """
                "enabled":
                {
                    "label": "Enabled",
                    "description": "If unchecked, this script will be disabled.",
                    "type": "bool",
                    "default_value": true
                },
                "elegoo_model":
                {
                    "label": "Neptune 3 Type",
                    "description": "The type of printer.",
                    "type": "enum",
                    "options":
                    {
                        "base": "Base",
                        "pro": "Pro/Plus/Max" 
                    },
                    "default_value": "pro"
                }
            """

        # Note: The version key is not the plugin version,  it's the data structure version.
        text = """{
            "name": "Elegoo Neptune 3 Thumbnail",
            "key": "CreateElegooNeptune3Thumbnail",
            "metadata": {},
            "version": 2,
            "settings":
            {
                <settings here>
            }
        }""".replace('<settings here>', ''.join(settings_text).strip()).strip()

        # with open(os.path.join(this_path, 'out.txt'), 'w') as file:
        #     file.write(text)
        return text

    def execute(self, data):
        # start with a large one, and shrink it later
        snapshot = Snapshot.snapshot(800, 800)
        if not snapshot:
            snapshot_gcode = [
                "; CreateElegooNeptune3Thumbnail script: Skipped thumbnail generation: couldn't take screenshot"
            ]
        else:
            snapshot_gcode = self._convertSnapshotToGcode(snapshot)

        for layer in data:
            layer_index = data.index(layer)
            lines = data[layer_index].split("\n")
            for line in lines:
                if line.startswith(";Generated with Cura"):
                    line_index = lines.index(line)
                    insert_index = line_index + 1
                    lines[insert_index:insert_index] = snapshot_gcode
                    break

            final_lines = "\n".join(lines)
            data[layer_index] = final_lines

        return data


def macos_check_quarantine(filepath: str) -> bool:
    """ Returns True if the macOS library is under quarantine, so a nice error message can be shown. """
    if Platform.isOSX():
        if not os.path.isfile(filepath):
            return False

        import subprocess
        # See if it's under quarantine still
        output = subprocess.check_output(['xattr', filepath]).decode().strip()
        Logger.log("d", "Library: {!r} quarantine attributes: {}".format(filepath, output))
        if 'com.apple.quarantine' in output:
            if 'com.apple.lastuseddate' in output:
                # Means they clicked open, giving it permission.
                return False
            else:
                # They didn't clear quarantine yet.
                return True
        else:
            # no quarantine flag.
            return False

    # Not macOS. Not sure if Linux or windows has something similar, these days.
    return False


def get_dll_filepath(subdir='lib') -> str:
    """ Returns the filepath to the dll that should be used. """
    if Platform.isOSX():
        filename = os.path.join(this_path, subdir, "libColPic.dylib")
    elif Platform.isLinux():
        filename = os.path.join(this_path, subdir, "libColPic.so")
    else:
        filename = os.path.join(this_path, subdir, "ColPic_X64.dll")
    return filename


def n3_base_encode_image(img, width: int, height: int, img_type: str) -> str:
    """ Convert the image to gcode.

    :param img:
    :param width:
    :param height:
    :param img_type:
    :return:
    """
    result = ""
    b_image = img.scaled(
        width, height,
        aspectRatioMode=Qt.AspectRatioMode.KeepAspectRatio,
        transformMode=Qt.TransformationMode.SmoothTransformation
    )

    img_size = b_image.size()
    result += img_type
    datasize = 0
    for i in range(img_size.height()):
        for j in range(img_size.width()):
            pixel_color = b_image.pixelColor(j, i)
            r = pixel_color.red() >> 3
            g = pixel_color.green() >> 2
            b = pixel_color.blue() >> 3
            rgb = (r << 11) | (g << 5) | b
            strHex = "%x" % rgb
            if len(strHex) == 3:
                strHex = '0' + strHex[0:3]
            elif len(strHex) == 2:
                strHex = '00' + strHex[0:2]
            elif len(strHex) == 1:
                strHex = '000' + strHex[0:1]
            if strHex[2:4] != '':
                result += strHex[2:4]
                datasize += 2
            if strHex[0:2] != '':
                result += strHex[0:2]
                datasize += 2
            if datasize >= 50:
                datasize = 0

        result += '\rM10086 ;'
        if i == img_size.height() - 1:
            result += "\r"

    return result


def neptune_3_pro_encode_image(img, width, height, img_type):
    """ Convert the image to a string, using the Elegoo provided libraries.

    These libraries come from Elegoo Cura:
        https://www.elegoo.com/pages/3d-printing-user-support
    in the Cura/plugins/MKS Plugin folder:
        ColPic_X64.dll: Windows
        libColPic.dylib: macOS
        libColPic.so: Linux

    I did not provide the libraries. They must be manually copied here because I don't know what the licensing is, and
    I don't know what's in them.

    :param img: the image to scale down, and insert into the gcode
    :param width: width to scale down the image
    :param height: height to scale down the image
    :param img_type: the type tag to add. I haven't tried to find out what this is.
    :return:
    """
    result = ""

    try:
        pDll = CDLL(get_dll_filepath())

        b_image = img.scaled(
            width, height,
            aspectRatioMode=Qt.AspectRatioMode.KeepAspectRatio,
            transformMode=Qt.TransformationMode.SmoothTransformation
        )
        # b_image.save(os.path.abspath("")+"\\test_"+str(width)+"_.png")
        # img.save(os.path.abspath("") + "\\testb_" + str(width) + "_.png")
        img_size = b_image.size()
        color16 = array('H')
        # Logger.log("d", "try == ")
        for i in range(img_size.height()):
            for j in range(img_size.width()):
                pixel_color = b_image.pixelColor(j, i)
                r = pixel_color.red() >> 3
                g = pixel_color.green() >> 2
                b = pixel_color.blue() >> 3
                rgb = (r << 11) | (g << 5) | b
                color16.append(rgb)

        # int ColPic_EncodeStr(U16* fromcolor16, int picw, int pich, U8* outputdata, int outputmaxtsize, int colorsmax);
        fromcolor16 = color16.tobytes()
        outputdata = array('B', [0] * img_size.height() * img_size.width()).tobytes()
        resultInt = pDll.ColPic_EncodeStr(fromcolor16, img_size.height(), img_size.width(), outputdata,
                                          img_size.height() * img_size.width(), 1024)

        data0 = str(outputdata).replace('\\x00', '')
        data1 = data0[2:len(data0) - 2]
        eachMax = 1024 - 8 - 1
        maxline = int(len(data1) / eachMax)
        appendlen = eachMax - 3 - int(len(data1) % eachMax)

        for i in range(len(data1)):
            if i == maxline * eachMax:
                result += '\r;' + img_type + data1[i]
            elif i == 0:
                result += img_type + data1[i]
            elif i % eachMax == 0:
                result += '\r' + img_type + data1[i]
            else:
                result += data1[i]
        result += '\r;'
        for j in range(appendlen):
            result += '0'

    except Exception as e:
        Logger.log("d", "Exception == " + str(e))
        result = ''

    return result + '\r'


def make_checkbox_message(text: str) -> str:
    """ Make a bunch of checkboxes as a way to print a multiline message in the PostProcessingPlugin GUI.
    lol. I can't figure out a better way to do this. The only element for display, rather than input, is "category",
    but it's not suitable. """
    text = text.strip().replace("\"", "'")  # double to single quote.

    entries = []

    spacer = """
        "spacer<index>_<index2>": {
            "label": "",
            "description": "Oops! Additional steps required!",
            "type": "bool",
            "default_value": false
        }
    """.strip()

    message = """
        "message<index>": {
            "label": "<msg>",
            "description": "Oops! Additional steps required!",
            "type": "bool",
            "default_value": false
        }
    """.strip()

    for i, line in enumerate(text.split('\n')):
        num_spacers = len(line) // 45
        # make sure it's even
        num_spacers += num_spacers % 2

        # word wrap is about 50 characters on my screen. no idea how to do this correctly.
        spacers = [
            spacer.replace('<index>', str(i)).replace('<index2>', str(spacer_i))
            for spacer_i in range(num_spacers)
        ]

        entries.extend(spacers[:len(spacers)//2])
        entries.append(message.replace('<index>', str(i)).replace('<msg>', line))
        entries.extend(spacers[len(spacers)//2:])

    settings_text = ',\n'.join(entries).strip()

    return settings_text
