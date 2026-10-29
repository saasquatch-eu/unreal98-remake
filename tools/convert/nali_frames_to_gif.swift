import Foundation
import ImageIO
import UniformTypeIdentifiers

guard CommandLine.arguments.count == 2 else {
    fatalError("usage: swift nali_frames_to_gif.swift <walk-preview-directory>")
}
let folder = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
let output = folder.appendingPathComponent("Nali1_WalkPreview_ue5.gif")
guard !FileManager.default.fileExists(atPath: output.path) else {
    fatalError("output already exists")
}
let paths = (0..<20).map { frame in
    folder.appendingPathComponent(String(format: "Nali1_WalkPreview_frame%02d_ue5.png", frame))
}
for path in paths {
    guard FileManager.default.fileExists(atPath: path.path) else {
        fatalError("missing frame: \(path.path)")
    }
}
guard let destination = CGImageDestinationCreateWithURL(output as CFURL, UTType.gif.identifier as CFString, paths.count, nil) else {
    fatalError("could not create GIF destination")
}
let globalProperties: [CFString: Any] = [
    kCGImagePropertyGIFDictionary: [kCGImagePropertyGIFLoopCount: 0]
]
CGImageDestinationSetProperties(destination, globalProperties as CFDictionary)
let frameProperties: [CFString: Any] = [
    kCGImagePropertyGIFDictionary: [
        kCGImagePropertyGIFDelayTime: 1.0 / 15.0,
        kCGImagePropertyGIFUnclampedDelayTime: 1.0 / 15.0
    ]
]
for path in paths {
    guard let source = CGImageSourceCreateWithURL(path as CFURL, nil),
          let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else {
        fatalError("could not read frame: \(path.path)")
    }
    CGImageDestinationAddImage(destination, image, frameProperties as CFDictionary)
}
guard CGImageDestinationFinalize(destination) else {
    fatalError("could not finalize GIF")
}
let bytes = try Data(contentsOf: output)
print("GIF_CREATED \(output.path) \(bytes.count)")
