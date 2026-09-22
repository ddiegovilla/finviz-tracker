from pathlib import Path
import subprocess

from AppKit import NSBitmapImageRep, NSGraphicsContext, NSImage, NSMakeRect, NSCompositingOperationCopy


root = Path(__file__).resolve().parent.parent
output = root / "build" / "Finviz Tracker.iconset"
output.mkdir(parents=True, exist_ok=True)
source = NSImage.alloc().initWithContentsOfFile_(str(root / "frontend" / "favicon.svg"))
if source is None:
    raise RuntimeError("Cannot read the existing application icon")
for size in (16, 32, 128, 256, 512):
    for scale in (1, 2):
        pixels = size * scale
        bitmap = NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
            None, pixels, pixels, 8, 4, True, False, "NSDeviceRGBColorSpace", 0, 0)
        NSGraphicsContext.saveGraphicsState()
        NSGraphicsContext.setCurrentContext_(NSGraphicsContext.graphicsContextWithBitmapImageRep_(bitmap))
        source.drawInRect_fromRect_operation_fraction_(NSMakeRect(0, 0, pixels, pixels), NSMakeRect(0, 0, 0, 0), NSCompositingOperationCopy, 1.0)
        NSGraphicsContext.restoreGraphicsState()
        filename = output / f"icon_{size}x{size}{'@2x' if scale == 2 else ''}.png"
        bitmap.representationUsingType_properties_(4, {}).writeToFile_atomically_(str(filename), True)
subprocess.run(["iconutil", "-c", "icns", str(output), "-o", str(root / "build" / "Finviz Tracker.icns")], check=True)
