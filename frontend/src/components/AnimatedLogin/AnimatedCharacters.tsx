import React, { useState, useEffect, useRef } from 'react'

interface AnimatedCharactersProps {
  isTyping?: boolean
  showPassword?: boolean
  passwordLength?: number
}

// 独立的眼球组件，内部自己监听鼠标
const EyeBall: React.FC<{
  size?: number
  pupilSize?: number
  maxDistance?: number
  eyeColor?: string
  pupilColor?: string
  isBlinking?: boolean
  forceLookX?: number
  forceLookY?: number
}> = ({
  size = 48,
  pupilSize = 16,
  maxDistance = 10,
  eyeColor = 'white',
  pupilColor = '#1a1a2e',
  isBlinking = false,
  forceLookX,
  forceLookY,
}) => {
  const [mouseX, setMouseX] = useState(0)
  const [mouseY, setMouseY] = useState(0)
  const eyeRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      setMouseX(e.clientX)
      setMouseY(e.clientY)
    }
    window.addEventListener('mousemove', handleMouseMove)
    return () => window.removeEventListener('mousemove', handleMouseMove)
  }, [])

  const calculatePupilPosition = () => {
    if (forceLookX !== undefined && forceLookY !== undefined) {
      return { x: forceLookX, y: forceLookY }
    }
    if (!eyeRef.current) return { x: 0, y: 0 }

    const eye = eyeRef.current.getBoundingClientRect()
    const eyeCenterX = eye.left + eye.width / 2
    const eyeCenterY = eye.top + eye.height / 2

    const deltaX = mouseX - eyeCenterX
    const deltaY = mouseY - eyeCenterY
    const distance = Math.min(Math.sqrt(deltaX ** 2 + deltaY ** 2), maxDistance)
    const angle = Math.atan2(deltaY, deltaX)

    return {
      x: Math.cos(angle) * distance,
      y: Math.sin(angle) * distance,
    }
  }

  const pupilPos = calculatePupilPosition()

  return (
    <div
      ref={eyeRef}
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
        flexShrink: 0,
      }}
    >
      {!isBlinking && (
        <div
          style={{
            width: pupilSize,
            height: pupilSize,
            backgroundColor: pupilColor,
            borderRadius: '50%',
            transform: `translate(${pupilPos.x}px, ${pupilPos.y}px)`,
            transition: 'transform 0.1s ease-out',
          }}
        />
      )}
    </div>
  )
}

export const AnimatedCharacters: React.FC<AnimatedCharactersProps> = ({
  isTyping = false,
  showPassword = false,
  passwordLength = 0,
}) => {
  const [mouseX, setMouseX] = useState(0)
  const [mouseY, setMouseY] = useState(0)
  const [isPurpleBlinking, setIsPurpleBlinking] = useState(false)
  const [isBlackBlinking, setIsBlackBlinking] = useState(false)
  const [isLookingAtEachOther, setIsLookingAtEachOther] = useState(false)
  const [isPurplePeeking, setIsPurplePeeking] = useState(false)

  const purpleRef = useRef<HTMLDivElement>(null)
  const blackRef = useRef<HTMLDivElement>(null)
  const yellowRef = useRef<HTMLDivElement>(null)
  const orangeRef = useRef<HTMLDivElement>(null)

  // 鼠标追踪
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      setMouseX(e.clientX)
      setMouseY(e.clientY)
    }
    window.addEventListener('mousemove', handleMouseMove)
    return () => window.removeEventListener('mousemove', handleMouseMove)
  }, [])

  // 紫色角色眨眼 - 递归随机
  useEffect(() => {
    const scheduleBlink = () => {
      const t = setTimeout(() => {
        setIsPurpleBlinking(true)
        setTimeout(() => {
          setIsPurpleBlinking(false)
          scheduleBlink()
        }, 150)
      }, Math.random() * 4000 + 3000)
      return t
    }
    const t = scheduleBlink()
    return () => clearTimeout(t)
  }, [])

  // 黑色角色眨眼 - 递归随机
  useEffect(() => {
    const scheduleBlink = () => {
      const t = setTimeout(() => {
        setIsBlackBlinking(true)
        setTimeout(() => {
          setIsBlackBlinking(false)
          scheduleBlink()
        }, 150)
      }, Math.random() * 4000 + 4000)
      return t
    }
    const t = scheduleBlink()
    return () => clearTimeout(t)
  }, [])

  // 输入时互相对视
  useEffect(() => {
    if (isTyping) {
      setIsLookingAtEachOther(true)
      const t = setTimeout(() => setIsLookingAtEachOther(false), 800)
      return () => clearTimeout(t)
    } else {
      setIsLookingAtEachOther(false)
    }
  }, [isTyping])

  // 显示密码时偷看
  useEffect(() => {
    if (passwordLength > 0 && showPassword) {
      const schedulePeek = () => {
        const t = setTimeout(() => {
          setIsPurplePeeking(true)
          setTimeout(() => {
            setIsPurplePeeking(false)
          }, 800)
        }, Math.random() * 3000 + 2000)
        return t
      }
      const t = schedulePeek()
      return () => clearTimeout(t)
    } else {
      setIsPurplePeeking(false)
    }
  }, [passwordLength, showPassword, isPurplePeeking])

  // 计算各角色的脸部偏移和身体倾斜
  const calculatePos = (ref: React.RefObject<HTMLDivElement | null>) => {
    if (!ref.current) return { faceX: 0, faceY: 0, bodySkew: 0 }
    const rect = ref.current.getBoundingClientRect()
    const centerX = rect.left + rect.width / 2
    const centerY = rect.top + rect.height / 3
    const deltaX = mouseX - centerX
    const deltaY = mouseY - centerY
    return {
      faceX: Math.max(-15, Math.min(15, deltaX / 20)),
      faceY: Math.max(-10, Math.min(10, deltaY / 30)),
      bodySkew: Math.max(-6, Math.min(6, -deltaX / 120)),
    }
  }

  const purplePos = calculatePos(purpleRef)
  const blackPos = calculatePos(blackRef)
  const yellowPos = calculatePos(yellowRef)
  const orangePos = calculatePos(orangeRef)

  const isHidingPassword = passwordLength > 0 && !showPassword

  return (
    <div
      style={{
        position: 'relative',
        width: 550,
        height: 420,
        userSelect: 'none',
      }}
    >
      {/* ===== 紫色高角色（后层左侧） ===== */}
      <div
        ref={purpleRef}
        style={{
          position: 'absolute',
          bottom: 0,
          left: 60,
          width: 180,
          height: isTyping || isHidingPassword ? 440 : 400,
          backgroundColor: '#6C3FF5',
          borderRadius: '10px 10px 0 0',
          zIndex: 1,
          transition: 'all 0.7s ease-in-out',
          transformOrigin: 'bottom center',
          transform:
            passwordLength > 0 && showPassword
              ? 'skewX(0deg)'
              : isTyping || isHidingPassword
              ? `skewX(${(purplePos.bodySkew || 0) - 12}deg) translateX(40px)`
              : `skewX(${purplePos.bodySkew}deg)`,
        }}
      >
        {/* 紫色角色眼睛 */}
        <div
          style={{
            position: 'absolute',
            display: 'flex',
            gap: 14,
            transition: 'all 0.7s ease-in-out',
            left:
              passwordLength > 0 && showPassword
                ? 20
                : isLookingAtEachOther
                ? 55
                : 45 + purplePos.faceX,
            top:
              passwordLength > 0 && showPassword
                ? 35
                : isLookingAtEachOther
                ? 65
                : 40 + purplePos.faceY,
          }}
        >
          <EyeBall
            size={18}
            pupilSize={7}
            maxDistance={5}
            eyeColor="white"
            pupilColor="#2D2D2D"
            isBlinking={isPurpleBlinking}
            forceLookX={
              passwordLength > 0 && showPassword
                ? isPurplePeeking ? 4 : -4
                : isLookingAtEachOther ? 3 : undefined
            }
            forceLookY={
              passwordLength > 0 && showPassword
                ? isPurplePeeking ? 5 : -4
                : isLookingAtEachOther ? 4 : undefined
            }
          />
          <EyeBall
            size={18}
            pupilSize={7}
            maxDistance={5}
            eyeColor="white"
            pupilColor="#2D2D2D"
            isBlinking={isPurpleBlinking}
            forceLookX={
              passwordLength > 0 && showPassword
                ? isPurplePeeking ? 4 : -4
                : isLookingAtEachOther ? 3 : undefined
            }
            forceLookY={
              passwordLength > 0 && showPassword
                ? isPurplePeeking ? 5 : -4
                : isLookingAtEachOther ? 4 : undefined
            }
          />
        </div>
      </div>

      {/* ===== 黑色矩形角色（中层） ===== */}
      <div
        ref={blackRef}
        style={{
          position: 'absolute',
          bottom: 0,
          left: 200,
          width: 120,
          height: isTyping || isHidingPassword ? 340 : 310,
          backgroundColor: '#2D2D2D',
          borderRadius: '8px 8px 0 0',
          zIndex: 2,
          transition: 'all 0.7s ease-in-out',
          transformOrigin: 'bottom center',
          transform: isTyping || isHidingPassword
            ? `skewX(${(blackPos.bodySkew || 0) + 10}deg) translateX(-30px)`
            : `skewX(${blackPos.bodySkew}deg)`,
        }}
      >
        {/* 黑色角色眼睛 */}
        <div
          style={{
            position: 'absolute',
            display: 'flex',
            gap: 10,
            transition: 'all 0.7s ease-in-out',
            left: isLookingAtEachOther ? 10 : 20 + blackPos.faceX,
            top: isLookingAtEachOther ? 65 : 40 + blackPos.faceY,
          }}
        >
          <EyeBall
            size={16}
            pupilSize={6}
            maxDistance={4}
            eyeColor="white"
            pupilColor="#6C3FF5"
            isBlinking={isBlackBlinking}
            forceLookX={isLookingAtEachOther ? -4 : undefined}
            forceLookY={isLookingAtEachOther ? 3 : undefined}
          />
          <EyeBall
            size={16}
            pupilSize={6}
            maxDistance={4}
            eyeColor="white"
            pupilColor="#6C3FF5"
            isBlinking={isBlackBlinking}
            forceLookX={isLookingAtEachOther ? -4 : undefined}
            forceLookY={isLookingAtEachOther ? 3 : undefined}
          />
        </div>
      </div>

      {/* ===== 橙色半圆形角色（前左层） ===== */}
      <div
        ref={orangeRef}
        style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          width: 130,
          height: 130,
          backgroundColor: '#FF9B6B',
          borderRadius: '65px 65px 0 0',
          zIndex: 3,
          transition: 'transform 0.4s ease-out',
          transformOrigin: 'bottom center',
          transform: `skewX(${orangePos.bodySkew * 0.5}deg)`,
        }}
      >
        {/* 橙色角色眼睛 */}
        <div
          style={{
            position: 'absolute',
            display: 'flex',
            gap: 16,
            left: 20 + orangePos.faceX,
            top: 30 + orangePos.faceY,
            transition: 'all 0.3s ease-out',
          }}
        >
          <EyeBall size={22} pupilSize={9} maxDistance={5} eyeColor="white" pupilColor="#1a1a2e" />
          <EyeBall size={22} pupilSize={9} maxDistance={5} eyeColor="white" pupilColor="#1a1a2e" />
        </div>
      </div>

      {/* ===== 黄色角色（前右层） ===== */}
      <div
        ref={yellowRef}
        style={{
          position: 'absolute',
          bottom: 0,
          right: 30,
          width: 140,
          height: 230,
          backgroundColor: '#E8D754',
          borderRadius: '70px 70px 10px 10px',
          zIndex: 3,
          transition: 'transform 0.4s ease-out',
          transformOrigin: 'bottom center',
          transform: `skewX(${yellowPos.bodySkew * 0.5}deg)`,
        }}
      >
        {/* 黄色角色眼睛 */}
        <div
          style={{
            position: 'absolute',
            display: 'flex',
            gap: 18,
            left: 22 + yellowPos.faceX,
            top: 55 + yellowPos.faceY,
            transition: 'all 0.3s ease-out',
          }}
        >
          <EyeBall size={26} pupilSize={10} maxDistance={6} eyeColor="white" pupilColor="#1a1a2e" />
          <EyeBall size={26} pupilSize={10} maxDistance={6} eyeColor="white" pupilColor="#1a1a2e" />
        </div>
        {/* 嘴巴 */}
        <div
          style={{
            position: 'absolute',
            bottom: 50,
            left: '50%',
            transform: 'translateX(-50%)',
            width: 40,
            height: 20,
            borderBottom: '4px solid #1a1a2e',
            borderRadius: '0 0 20px 20px',
          }}
        />
      </div>
    </div>
  )
}

export default AnimatedCharacters
