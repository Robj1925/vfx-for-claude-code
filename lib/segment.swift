// Person matte for every frame of a video, streamed as raw 8-bit gray frames to stdout.
// usage: segment <video> [accurate|balanced]
// Output frame size = input frame size. Frame count = decoded frame count (logged to stderr).
import Foundation
import AVFoundation
import Vision
import CoreImage

let args = CommandLine.arguments
guard args.count >= 2 else { FileHandle.standardError.write("usage: segment <video> [accurate|balanced]\n".data(using: .utf8)!); exit(2) }
let asset = AVURLAsset(url: URL(fileURLWithPath: args[1]))
let track = asset.tracks(withMediaType: .video)[0]
let reader = try AVAssetReader(asset: asset)
let out = AVAssetReaderTrackOutput(track: track, outputSettings: [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA])
out.alwaysCopiesSampleData = false
reader.add(out); reader.startReading()

let req = VNGeneratePersonSegmentationRequest()
req.qualityLevel = (args.count > 2 && args[2] == "balanced") ? .balanced : .accurate
req.outputPixelFormat = kCVPixelFormatType_OneComponent8
let ctx = CIContext(options: [.workingColorSpace: NSNull()])
let stdout = FileHandle.standardOutput
var n = 0
while let sb = out.copyNextSampleBuffer() {
    guard let pb = CMSampleBufferGetImageBuffer(sb) else { continue }
    let W = CVPixelBufferGetWidth(pb), H = CVPixelBufferGetHeight(pb)
    var bytes = [UInt8](repeating: 0, count: W * H)
    let h = VNImageRequestHandler(cvPixelBuffer: pb, options: [:])
    if (try? h.perform([req])) != nil, let m = req.results?.first?.pixelBuffer {
        var ci = CIImage(cvPixelBuffer: m)
        ci = ci.transformed(by: CGAffineTransform(scaleX: CGFloat(W) / ci.extent.width, y: CGFloat(H) / ci.extent.height))
        bytes.withUnsafeMutableBytes { p in
            ctx.render(ci, toBitmap: p.baseAddress!, rowBytes: W, bounds: CGRect(x: 0, y: 0, width: W, height: H),
                       format: .L8, colorSpace: nil)
        }
    }
    stdout.write(Data(bytes))
    n += 1
    if n % 300 == 0 { FileHandle.standardError.write("  matte \(n) frames\n".data(using: .utf8)!) }
}
FileHandle.standardError.write("matte done: \(n) frames\n".data(using: .utf8)!)
