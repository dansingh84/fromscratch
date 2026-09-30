# OMC transport mapping - working note (pre-standardization)

Pattern follows RFC 9134 / ST 2110-22 practice for JPEG XS so facility
integration is familiar:

- **Elementary stream**: the .omc framing (32-byte stream header + fixed
  F-byte frames) is already CBR and self-describing; frame boundaries are
  computable from the header alone (F = nslices x bits_per_slice/8).
- **RTP (proposed)**: one frame per RTP packet train, marker bit on the
  final packet of each frame; packetization on slice boundaries (each
  slice is independently decodable after the stream header, CRC-protected;
  packet loss maps to slice loss, which the codec conceals and repairs
  within R frames by design). Stream header repeated periodically
  (once per refresh period) for late joiners.
- **ST 2110-style essence**: as with -22, a constant-bitrate compressed
  video essence with SDP signaling of (width, height, fps, depth, chroma,
  bpp, R, mode). The omc_config.schema.json fields map 1:1 onto SDP
  fmtp parameters; NMOS registration mirrors BCP-006-01.
- **File carriage**: raw .omc is seekable by arithmetic (frame k at
  offset 32 + k x F); MXF/ISOBMFF mappings are future work, priority per
  market note (boundary-only for the media-server ecosystem).

This note becomes a real payload spec when the bitstream freezes.
