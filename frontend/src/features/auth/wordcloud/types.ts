export type WordColor = 'red' | 'grey' | 'light-grey' | 'white';

export interface WordItem {
  id: string;
  text: string;
  color: WordColor;
  x: number; // Left percentage position on canvas (0 to 100)
  y: number; // Top percentage position on canvas (0 to 100)
  isVertical?: boolean;
  isMain?: boolean; // Represents "心选电商"
  direction: 'top' | 'bottom' | 'left' | 'right';
  distance?: number; // Distance from center
  sequence?: number; // Sorted launch sequence number
}
