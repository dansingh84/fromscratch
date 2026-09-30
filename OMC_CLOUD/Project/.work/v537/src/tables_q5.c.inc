/* Q5F block-skip-flag tANS count tables.  DERIVED FROM CORPUS STATISTICS, two
 * passes: (1) the read-only OMC_Q5STAT census supplied a bootstrap set from the
 * flag field the scheme WOULD produce at the v5.2 operating point; (2) the
 * scheme was then built with that set and its LIVE flag field harvested
 * (OMC_Q5MEASURE, Q5HIST) on dng + cityalley + bosphorus, 1920x1080 422/10,
 * 0.5 bpp, 6 frames, K=16 -- and these are those counts, normalised to
 * OMC_TANS_L = 1024 with a floor of 1 on every symbol so no symbol is
 * un-codable.  A new context must NOT share a coefficient table: the flag
 * alphabet is binary/ternary and the coefficient distributions do not fit it.
 *   ctx 0-3: block flag, ctx = 2*skip[left-2] + skip[left-1]
 *   ctx 4-7: band-unit symbol {0 none, 1 all, 2 mixed},
 *            ctx = 4 + 2*(band >= 7) + inter
 * Observed p(skip): ctx0 0.259  ctx1 0.661  ctx2 0.440  ctx3 0.873
 */
const uint16_t omc_tans_counts_q5[OMC_NQ5CTX][OMC_NSYM] = {
 {749,261,1,1,1,1,1,1,1,1,1,1,1,1,1,1},   /* raw: 68715,23964,0 */
 {342,668,1,1,1,1,1,1,1,1,1,1,1,1,1,1},   /* raw: 12108,23623,0 */
 {566,444,1,1,1,1,1,1,1,1,1,1,1,1,1,1},   /* raw: 16462,12922,0 */
 {128,882,1,1,1,1,1,1,1,1,1,1,1,1,1,1},   /* raw: 18267,125668,0 */
 {477,124,410,1,1,1,1,1,1,1,1,1,1,1,1,1},   /* raw: 2513,656,2162 */
 {706,20,285,1,1,1,1,1,1,1,1,1,1,1,1,1},   /* raw: 9298,267,3752 */
 {1,670,340,1,1,1,1,1,1,1,1,1,1,1,1,1},   /* raw: 4,3929,1991 */
 {1,75,935,1,1,1,1,1,1,1,1,1,1,1,1,1},   /* raw: 0,154,1914 */
};
