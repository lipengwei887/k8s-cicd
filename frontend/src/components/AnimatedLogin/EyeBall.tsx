import React from 'react'
import Pupil from './Pupil'

interface EyeBallProps {
  size?: number
  pupilSize?: number
  maxDistance?: number
  eyeColor?: string
  pupilColor?: string
  isBlinking?: boolean
  forceLookX?: number
  forceLookY?: number
  mouseX: number
  mouseY: number
  parentRect: DOMRect | null
}

const EyeBall: React.FC<EyeBallProps> = ({
  size = 48,
  pupilSize = 16,
  maxDistance = 10,
  eyeColor = '#ffffff',
  pupilColor = '#1a1a2e',
  isBlinking = false,
  forceLookX,
  forceLookY,
  mouseX,
  mouseY,
  parentRect,
}) => {
  return (
    <div
      className="eye-ball"
      style={{
        width: size,
        height: isBlinking ? 2 : size,
        backgroundColor: eyeColor,
        borderRadius: '50%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        overflow: 'hidden',
        transition: 'height 0.15s ease-out',
        boxShadow: 'inset 0 2px 4px rgba(0,0,0,0.1)',
      }}
    >
      {!isBlinking && (
        <Pupil
          size={pupilSize}
          maxDistance={maxDistance}
          pupilColor={pupilColor}
          forceLookX={forceLookX}
          forceLookY={forceLookY}
          mouseX={mouseX}
          mouseY={mouseY}
          parentRect={parentRect}
        />
      )}
    </div>
  )
}

export default EyeBall
