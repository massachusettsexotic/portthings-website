// QR code PNG with macOS CoreImage: swift make_qr.swift <text> <out.png>   (1024 px, quiet zone, black on white)
import CoreImage
import AppKit
let args = CommandLine.arguments
let f = CIFilter(name: "CIQRCodeGenerator")!
f.setValue(args[1].data(using: .utf8), forKey: "inputMessage")
f.setValue("M", forKey: "inputCorrectionLevel")
let qr = f.outputImage!
let scale = 1024.0 / (qr.extent.width + 8)
let padded = qr.transformed(by: CGAffineTransform(translationX: 4, y: 4))
    .composited(over: CIImage(color: .white).cropped(to: CGRect(x: 0, y: 0, width: qr.extent.width + 8, height: qr.extent.height + 8)))
    .transformed(by: CGAffineTransform(scaleX: scale, y: scale))
let rep = NSBitmapImageRep(ciImage: padded)
try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: args[2]))
