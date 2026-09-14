import { List, type RowComponentProps } from 'react-window';

interface VirtualListProps<T> {
  items: T[];
  height: number;
  itemHeight: number;
  renderItem: (item: T, index: number) => React.ReactNode;
}

function Row<T>({ index, style, ariaAttributes, items, renderItem }: RowComponentProps<Pick<VirtualListProps<T>, 'items' | 'renderItem'>>) {
  return <div style={style} {...ariaAttributes}>{renderItem(items[index], index)}</div>;
}

export function VirtualList<T>({ items, height, itemHeight, renderItem }: VirtualListProps<T>) {
  return (
    <List
      style={{ height, width: '100%' }}
      rowCount={items.length}
      rowHeight={itemHeight}
      rowComponent={Row<T>}
      rowProps={{ items, renderItem }}
    />
  );
}
