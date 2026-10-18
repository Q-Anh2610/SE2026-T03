const illustrations = [
  { file: 'chair', name: 'Ghế gỗ', description: 'Lưng ghế uốn cong, mặt ngồi đan và sắc gỗ tự nhiên.' },
  { file: 'lamp', name: 'Đèn bàn', description: 'Chụp đèn vòm, bề mặt bóng với sắc xanh cobalt.' },
  { file: 'vase', name: 'Bình gốm', description: 'Dáng bình tròn, hai quai nhỏ và bề mặt đất nung mộc.' },
  { file: 'stool', name: 'Ghế chrome', description: 'Khung kim loại thanh mảnh kết hợp mặt ngồi màu đen.' },
  { file: 'arch', name: 'Kiến trúc', description: 'Vòm cửa và bậc thang trong một khối màu trắng ngà.' },
  { file: 'plant', name: 'Cây cảnh', description: 'Tán lá xanh đậm trong chậu trụ màu xanh dịu.' },
]

export function DiscoveryGallery() {
  return (
    <section className="discovery-gallery" aria-label="Hình ảnh 3D">
      {illustrations.map(({ file, name, description }) => (
        <figure className="discovery-tile" key={file}>
          <img src={`${import.meta.env.BASE_URL}images/discovery/${file}.webp`}
            alt={`Ảnh minh họa 3D: ${name}`} loading="lazy" decoding="async" width="768" height="768" />
          <figcaption>
            <h2>{name}</h2>
            <p>{description}</p>
          </figcaption>
        </figure>
      ))}
    </section>
  )
}
