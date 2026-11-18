const illustrations = [
  { file: 'chair', name: 'Ghế gỗ', description: 'Lưng cong · mây đan · gỗ sáng' },
  { file: 'lamp', name: 'Đèn bàn', description: 'Chụp vòm · xanh cobalt' },
  { file: 'stool', name: 'Ghế chrome', description: 'Khung kim loại · mặt đen' },
  { file: 'plant', name: 'Cây cảnh', description: 'Lá xanh · chậu trụ' },
]

export function DiscoveryGallery({ onSelectQuery }: { onSelectQuery: (query: string) => void }) {
  return (
    <section className="discovery-gallery" aria-labelledby="discovery-title">
      <div className="discovery-heading">
        <div>
          <h2 id="discovery-title">Bạn đang tìm gì?</h2>
        </div>
        <span>Chọn một mẫu để điền truy vấn.</span>
      </div>
      <div className="discovery-grid">
        {illustrations.map(({ file, name, description }) => (
          <button
            className="discovery-tile"
            key={file}
            type="button"
            onClick={() => onSelectQuery(name)}
            aria-label={`Điền gợi ý tìm kiếm: ${name}`}
          >
            <span className="discovery-image-wrap">
              <img src={`${import.meta.env.BASE_URL}images/discovery/${file}.webp`}
                alt="" loading="lazy" decoding="async" width="768" height="768" />
            </span>
            <span className="discovery-tile-copy">
              <strong>{name}</strong>
              <span>{description}</span>
            </span>
            <span className="discovery-tile-arrow" aria-hidden="true">↗</span>
          </button>
      ))}
      </div>
    </section>
  )
}
