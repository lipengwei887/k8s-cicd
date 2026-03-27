import React, { useEffect, useRef } from 'react'

interface PupilProps {
  size?: number
  maxDistance?: number
  pupilColor?: string
  forceLookX?: number
  forceLookY?: number
  mouseX: number
  mouseY: number
  parentRect: DOMRect | null
}

const Pupil: React.FC<PupilProps> = ({
  size = 12,
  maxDistance = 5,
  pupilColor = '#1a1a2e',
  forceLookX,
  forceLookY,
  mouseX,
  mouseY,
  parentRect,
}) => {
  const pupilRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!pupilRef.current || !parentRect) return

    const pupil = pupilRef.current
    const pupilRect = pupil.getBoundingClientRect()
    const pupilCenterX = pupilRect.left + pupilRect.width / 2
    const pupilCenterY = pupilRect.top + pupilRect.height / 2

    let deltaX = mouseX - pupilCenterX
    let deltaY = mouseY - pupilCenterY

    // 如果有强制看向的方向
    if (forceLookX !== undefined && forceLookY !== undefined) {
      deltaX = forceLookX * 100
      deltaY = forceLookY * 100
    }

    const angle = Math.atan2(deltaY, deltaX)
    const distance = Math.min(
      Math.sqrt(deltaX * deltaX + deltaY * deltaY) / 20,
      maxDistance
    )

    const x = Math.cos(angle) * distance
    const y = Math.sin(angle) * distance

    pupil.style.transform = `translate(${x}px, ${y}px)`
  }, [mouseX, mouseY, parentRect, maxDistance, forceLookX, forceLookY])

  return (
    <div
      ref={pupilRef}
      className="pupil"
      style={{
        width: size,
        height: size,
        backgroundColor: pupilColor,
        borderRadius: '50%',
        transition: 'transform 0.1s ease-out',
      }}
    />
  )
}

export default Pupil
