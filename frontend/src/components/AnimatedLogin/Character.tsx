import React from 'react'
import EyeBall from './EyeBall'

interface CharacterProps {
  type: 'purple' | 'black' | 'orange' | 'yellow'
  mouseX: number
  mouseY: number
  parentRect: DOMRect | null
  isBlinking?: boolean
  isLookingAtEachOther?: boolean
  isPeeking?: boolean
  bodyTilt?: number
  faceOffset?: { x: number; y: number }
}

const Character: React.FC<CharacterProps> = ({
  type,
  mouseX,
  mouseY,
  parentRect,
  isBlinking = false,
  isLookingAtEachOther = false,
  isPeeking = false,
  bodyTilt = 0,
  faceOffset = { x: 0, y: 0 },
}) => {
  // 根据类型定义角色样式
  const characterStyles = {
    purple: {
      containerClass: 'character-purple',
      bodyColor: '#6C3FF5',
      width: 80,
      height: 140,
      borderRadius: '40px 40px 20px 20px',
      eyeSize: 32,
      pupilSize: 12,
      eyeSpacing: 36,
      eyeTop: 35,
    },
    black: {
      containerClass: 'character-black',
      bodyColor: '#2D2D2D',
      width: 70,
      height: 100,
      borderRadius: '35px 35px 15px 15px',
      eyeSize: 28,
      pupilSize: 10,
      eyeSpacing: 30,
      eyeTop: 30,
    },
    orange: {
      containerClass: 'character-orange',
      bodyColor: '#FF9B6B',
      width: 60,
      height: 60,
      borderRadius: '30px 30px 0 0',
      eyeSize: 20,
      pupilSize: 8,
      eyeSpacing: 22,
      eyeTop: 20,
    },
    yellow: {
      containerClass: 'character-yellow',
      bodyColor: '#E8D754',
      width: 65,
      height: 80,
      borderRadius: '32px 32px 20px 20px',
      eyeSize: 24,
      pupilSize: 9,
      eyeSpacing: 26,
      eyeTop: 25,
    },
  }

  const style = characterStyles[type]

  // 计算眼睛看向的方向
  let leftEyeLook = { x: undefined as number | undefined, y: undefined as number | undefined }
  let rightEyeLook = { x: undefined as number | undefined, y: undefined as number | undefined }

  if (isLookingAtEachOther) {
    // 相互看向对方
    if (type === 'purple') {
      leftEyeLook = { x: -1, y: 0.3 }
      rightEyeLook = { x: -1, y: 0.3 }
    } else if (type === 'black') {
      leftEyeLook = { x: 1, y: 0.3 }
      rightEyeLook = { x: 1, y: 0.3 }
    }
  } else if (isPeeking && type === 'purple') {
    // 偷看密码 - 向下看
    leftEyeLook = { x: 0, y: 1 }
    rightEyeLook = { x: 0, y: 1 }
  }

  return (
    <div
      className={`character ${style.containerClass}`}
      style={{
        width: style.width,
        height: style.height,
        backgroundColor: style.bodyColor,
        borderRadius: style.borderRadius,
        transform: `skewX(${bodyTilt}deg)`,
        transition: 'transform 0.3s ease-out',
        position: 'relative',
        display: 'flex',
        justifyContent: 'center',
      }}
    >
      {/* 脸部容器 */}
      <div
        className="character-face"
        style={{
          position: 'absolute',
          top: style.eyeTop,
          transform: `translate(${faceOffset.x}px, ${faceOffset.y}px)`,
          transition: 'transform 0.3s ease-out',
          display: 'flex',
          gap: style.eyeSpacing - style.eyeSize,
        }}
      >
        <EyeBall
          size={style.eyeSize}
          pupilSize={style.pupilSize}
          maxDistance={style.eyeSize / 4}
          isBlinking={isBlinking}
          forceLookX={leftEyeLook.x}
          forceLookY={leftEyeLook.y}
          mouseX={mouseX}
          mouseY={mouseY}
          parentRect={parentRect}
        />
        <EyeBall
          size={style.eyeSize}
          pupilSize={style.pupilSize}
          maxDistance={style.eyeSize / 4}
          isBlinking={isBlinking}
          forceLookX={rightEyeLook.x}
          forceLookY={rightEyeLook.y}
          mouseX={mouseX}
          mouseY={mouseY}
          parentRect={parentRect}
        />
      </div>

      {/* 黄色角色的嘴巴 */}
      {type === 'yellow' && (
        <div
          className="character-mouth"
          style={{
            position: 'absolute',
            bottom: 20,
            width: 24,
            height: 12,
            borderBottom: '3px solid #2D2D2D',
            borderRadius: '0 0 12px 12px',
          }}
        />
      )}
    </div>
  )
}

export default Character
