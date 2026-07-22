import type { WordItem } from './types';

export const TEMPLATE_WORDS: Omit<WordItem, 'distance' | 'sequence'>[] = [
  { id: 'main-title', text: '企业文化', color: 'white', x: 43.55, y: 43.5, isMain: true, direction: 'top' },
  { id: 'tupo', text: '突破', color: 'grey', x: 63.5, y: 34.5, direction: 'right' },
  { id: 'breakthrough', text: 'BREAK THROUGH', color: 'light-grey', x: 81.0, y: 40.5, direction: 'right' },
  { id: 'gongtong', text: '沟通即效率', color: 'red', x: 59.25, y: 17.25, direction: 'top' },
  { id: 'gotoalllengths', text: 'GO TO ALL LENGTHS', color: 'light-grey', x: 56.25, y: 26.5, direction: 'top' },
  { id: 'xingdong', text: '行动', color: 'grey', x: 38.25, y: 17.5, isVertical: true, direction: 'top' },
  { id: 'effort', text: 'EFFORT', color: 'light-grey', x: 42.75, y: 18.25, isVertical: true, direction: 'top' },
  { id: 'yongzheng', text: '永争第一', color: 'grey', x: 77.0, y: 27.5, direction: 'right' },
  { id: 'gongchuang', text: '共创即共赢', color: 'red', x: 20.0, y: 22.5, direction: 'left' },
  { id: 'keeploving', text: 'KEEP LOVING', color: 'light-grey', x: 14.5, y: 36.0, direction: 'left' },
  { id: 'jiandanzhijie', text: '简单直接', color: 'grey', x: 22.5, y: 47.75, direction: 'left' },
  { id: 'surpassyourself', text: 'SURPASS YOURSELF', color: 'light-grey', x: 20.5, y: 58.5, direction: 'left' },
  { id: 'juejuetangping', text: '拒绝躺平', color: 'grey', x: 39.65, y: 60.0, direction: 'bottom' },
  { id: 'yonghujihuoban', text: '用户即伙伴', color: 'red', x: 31.5, y: 70.0, direction: 'left' },
  { id: 'nevergiveup', text: 'NEVER GIVE UP', color: 'light-grey', x: 34.0, y: 80.5, direction: 'bottom' },
  { id: 'taidu', text: '态度', color: 'grey', x: 17.0, y: 77.75, isVertical: true, direction: 'left' },
  { id: 'baochireai', text: '保持热爱', color: 'grey', x: 39.0, y: 90.0, direction: 'bottom' },
  { id: 'jianchi', text: '坚持', color: 'grey', x: 53.0, y: 70.0, isVertical: true, direction: 'bottom' },
  { id: 'persist', text: 'PERSIST', color: 'light-grey', x: 47.3, y: 75.5, isVertical: true, direction: 'bottom' },
  { id: 'objective', text: 'OBJECTIVE', color: 'light-grey', x: 63.5, y: 62.0, direction: 'right' },
  { id: 'mubiao', text: '目标', color: 'grey', x: 78.5, y: 64.25, direction: 'right' },
  { id: 'dream', text: 'DREAM', color: 'light-grey', x: 62.0, y: 73.5, direction: 'bottom' },
  { id: 'reaijizhuanye', text: '热爱即专业', color: 'red', x: 63.75, y: 90.5, direction: 'bottom' },
  { id: 'chuangxinjishengcun', text: '创新即生存', color: 'red', x: 72.5, y: 49.5, direction: 'right' },
];

export function getTemplateWords(launchMode: string): WordItem[] {
  const cx = 43.55;
  const cy = 43.5;

  const withDistance = TEMPLATE_WORDS.map((w) => {
    let dist = 0;
    if (!w.isMain) {
      dist = Math.sqrt((w.x - cx) * (w.x - cx) + (w.y - cy) * (w.y - cy));
    }
    return { ...w, distance: dist } as WordItem;
  });

  const mainItem = withDistance.find((w) => w.isMain);
  const regularItems = withDistance.filter((w) => !w.isMain);

  regularItems.sort((a, b) => (a.distance || 0) - (b.distance || 0));

  const sorted = mainItem ? [mainItem, ...regularItems] : regularItems;

  return sorted.map((w, index) => {
    let finalDirection = w.direction;

    if (launchMode === 'opposite') {
      const oppositions: Record<string, 'top' | 'bottom' | 'left' | 'right'> = {
        top: 'bottom', bottom: 'top', left: 'right', right: 'left',
      };
      finalDirection = oppositions[w.direction] || w.direction;
    } else if (launchMode === 'alternate') {
      const directions: ('top' | 'bottom' | 'left' | 'right')[] = ['top', 'right', 'bottom', 'left'];
      finalDirection = w.isMain ? 'top' : directions[index % 4];
    }

    return { ...w, direction: finalDirection, sequence: index + 1 };
  });
}
