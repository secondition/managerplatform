import React, { useEffect, useState } from 'react';
import { motion } from 'motion/react';
import type { WordItem } from './types';
import { getTemplateWords } from './templateWords';

function getWordStyles(w: WordItem): React.CSSProperties {
  const base: React.CSSProperties = {
    fontFamily: '"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Inter", sans-serif',
    whiteSpace: 'nowrap',
    lineHeight: 1.05,
    userSelect: 'none',
  };

  if (w.isMain) {
    return {
      ...base,
      width: '27.5cqw',
      height: '8.2cqw',
      fontSize: '3.5cqw',
      fontWeight: '900',
      letterSpacing: '0.55cqw',
      color: '#FFFFFF',
      backgroundColor: '#B90F24',
      borderRadius: '0.1cqw',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      paddingLeft: '0.275cqw',
    };
  }

  // Red text
  if (w.color === 'red') {
    return { ...base, fontSize: '3.5cqw', fontWeight: '900', color: '#B90F24', letterSpacing: '0.05cqw' };
  }

  // Grey text
  if (w.color === 'grey') {
    if (w.id === 'tupo') {
      return { ...base, fontSize: '4.5cqw', fontWeight: '900', color: '#555555', letterSpacing: '-0.05cqw' };
    }
    if (w.id === 'xingdong' || w.id === 'taidu') {
      return { ...base, fontSize: '5.1cqw', fontWeight: '900', color: '#555555', lineHeight: 0.88 };
    }
    if (w.id === 'jianchi') {
      return { ...base, fontSize: '4.8cqw', fontWeight: '900', color: '#555555', lineHeight: 0.88 };
    }
    if (w.id === 'jiandanzhijie' || w.id === 'mubiao') {
      return { ...base, fontSize: '2.9cqw', fontWeight: '800', color: '#555555' };
    }
    if (w.id === 'yongzheng') {
      return { ...base, fontSize: '2.4cqw', fontWeight: '700', color: '#555555' };
    }
    if (w.id === 'juejuetangping' || w.id === 'baochireai') {
      return { ...base, fontSize: '2.2cqw', fontWeight: '700', color: '#555555' };
    }
    return { ...base, fontSize: '2.0cqw', fontWeight: '700', color: '#555555' };
  }

  // Light-grey (English)
  if (w.color === 'light-grey') {
    const englishBase: React.CSSProperties = {
      ...base,
      fontFamily: '"Inter", sans-serif',
      fontWeight: '700',
      color: '#BBBBBB',
      textTransform: 'uppercase',
    };

    if (w.id === 'effort' || w.id === 'persist') {
      return { ...englishBase, fontSize: '1.7cqw', lineHeight: 1.0 };
    }
    if (w.id === 'keeploving') {
      return { ...englishBase, fontSize: '2.2cqw', letterSpacing: '0.12em' };
    }
    if (w.id === 'surpassyourself') {
      return { ...englishBase, fontSize: '2.0cqw', letterSpacing: '0.12em' };
    }
    if (w.id === 'nevergiveup') {
      return { ...englishBase, fontSize: '1.9cqw', letterSpacing: '0.12em' };
    }
    if (w.id === 'gotoalllengths' || w.id === 'breakthrough') {
      return { ...englishBase, fontSize: '1.6cqw', letterSpacing: '0.12em' };
    }
    if (w.id === 'objective') {
      return { ...englishBase, fontSize: '2.1cqw', letterSpacing: '0.12em' };
    }
    if (w.id === 'dream') {
      return { ...englishBase, fontSize: '2.4cqw', letterSpacing: '0.15em' };
    }
    return { ...englishBase, fontSize: '1.5cqw', letterSpacing: '0.1em' };
  }

  return base;
}

/**
 * Login screen culture word cloud template.
 * Rendered as a fixed, transparent, non-interactive layer behind the login card,
 * layered on top of the body's radial-gradient glow. Words fly in once on mount.
 */
export const CultureWordCloudTemplate: React.FC = () => {
  const [words, setWords] = useState<WordItem[]>([]);

  useEffect(() => {
    setWords(getTemplateWords('closest'));
  }, []);

  return (
    <div
      aria-hidden
      className="fixed inset-0 z-0 flex items-center justify-start overflow-hidden pointer-events-none select-none"
    >
      <div
        className="w-[70vw] max-w-[1000px] aspect-[2.35/1] relative @container ml-[3vw]"
      >
        {words.map((w) => {
          const customWordStyles = getWordStyles(w);

          // Launch from just outside the canvas boundary based on direction.
          const startX = w.direction === 'left' ? '-120%' : w.direction === 'right' ? '120%' : '0%';
          const startY = w.direction === 'top' ? '-120%' : w.direction === 'bottom' ? '120%' : '0%';
          const delayTime = w.isMain ? 0 : ((w.sequence || 2) - 1) * 0.12;

          return (
            <div
              key={w.id}
              className="absolute"
              style={{ left: `${w.x}%`, top: `${w.y}%`, transform: 'translate(-50%, -50%)' }}
            >
              <motion.div
                initial={w.isMain ? { opacity: 0, scale: 0.9 } : { x: startX, y: startY, opacity: 0, scale: 0.8 }}
                animate={{ x: '0%', y: '0%', opacity: 1, scale: 1 }}
                transition={{
                  duration: w.isMain ? 0.45 : 1.15,
                  delay: delayTime,
                  ease: [0.16, 1, 0.3, 1],
                }}
                style={customWordStyles}
              >
                {w.isVertical ? (
                  <div className="flex flex-col items-center justify-center gap-[0.22cqw]">
                    {w.text.split('').map((char, index) => (
                      <span key={index} className="block select-none">
                        {char}
                      </span>
                    ))}
                  </div>
                ) : (
                  w.text
                )}
              </motion.div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
