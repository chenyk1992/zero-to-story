import { useMemo, useState } from 'react';
import type { FlowNode } from './types';
import { Icon, type IconName } from './Icon';
import { mediaUrl } from './api';
import { categoryForNode, categoryLabelForNode, mediaCountForNode, nodeSearchText, type StoryNodeData, type StoryNodeType } from './workspace';

const ITEMS: Array<{ type: StoryNodeType; label: string; hint: string; icon: IconName }> = [
  { type: 'document', label: '文档', hint: '故事板或章节笔记', icon: 'document' },
  { type: 'section', label: '分区', hint: '组织场景、镜头与角色', icon: 'section' },
  { type: 'asset', label: '素材', hint: '图片、视频或音频', icon: 'asset' },
  { type: 'image', label: '图片', hint: '图片创作卡，选择可用生成方式', icon: 'image' },
  { type: 'video', label: '视频', hint: '视频创作卡，选择可用生成方式', icon: 'video' },
];

const FILTERS: Array<{ id: string; label: string; icon: IconName }> = [
  { id: '', label: '全部', icon: 'grid' },
  { id: 'character', label: '角色参考', icon: 'character' },
  { id: 'storyboard', label: '故事板', icon: 'storyboard' },
  { id: 'board', label: '电影画面分镜板', icon: 'board' },
  { id: 'image', label: '图片', icon: 'image' },
  { id: 'video', label: '视频', icon: 'video' },
  { id: 'document', label: '文档', icon: 'document' },
];

interface PaletteProps {
  nodes: FlowNode[];
  selectedId?: string;
  onAdd: (type: StoryNodeType) => void;
  onSelect: (nodeId: string) => void;
  collapsed?: boolean;
  onToggle?: () => void;
}

export function Palette({ nodes, selectedId, onAdd, onSelect, collapsed = false, onToggle }: PaletteProps) {
  const [filter, setFilter] = useState('');
  const [search, setSearch] = useState('');
  const storyData = (node: FlowNode) => node.data as unknown as StoryNodeData;
  const assetNodes = useMemo(() => nodes.filter((node) => storyData(node).nodeType !== 'section'), [nodes]);
  const counts = useMemo(() => FILTERS.reduce<Record<string, number>>((result, item) => {
    result[item.id] = item.id ? assetNodes.filter((node) => categoryForNode({ data: storyData(node) }) === item.id).length : assetNodes.length;
    return result;
  }, {}), [assetNodes]);
  const mediaCount = useMemo(() => assetNodes.reduce((count, node) => count + mediaCountForNode({ data: storyData(node) }), 0), [assetNodes]);
  const visibleNodes = useMemo(() => assetNodes.filter((node) => {
    const matchesFilter = !filter || categoryForNode({ data: storyData(node) }) === filter;
    const matchesSearch = !search.trim() || nodeSearchText({ id: node.id, data: storyData(node) }).includes(search.trim().toLocaleLowerCase());
    return matchesFilter && matchesSearch;
  }), [assetNodes, filter, search]);

  const dragStart = (event: React.DragEvent<HTMLButtonElement>, type: StoryNodeType) => {
    event.dataTransfer.effectAllowed = 'copy';
    event.dataTransfer.setData('application/x-canvas-node', type);
  };

  return (
    <aside className={`palette${collapsed ? ' palette-collapsed' : ''}`} aria-label="故事资产导航">
      <div className="palette-brand">{!collapsed && <strong>章节资产 <small>{assetNodes.length}</small></strong>}<button className="palette-collapse" type="button" onClick={onToggle} title={collapsed ? '展开资产栏' : '收起资产栏'} aria-label={collapsed ? '展开资产栏' : '收起资产栏'}><Icon name="panelLeft" /></button></div>
      {!collapsed && <>
        <label className="asset-search"><Icon name="search" size={16} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索角色、镜头…" aria-label="搜索章节资产" />{search && <button type="button" onClick={() => setSearch('')} aria-label="清除搜索"><Icon name="close" size={14} /></button>}</label>
        <nav className="asset-filters" aria-label="资产分类">
          {FILTERS.map((item) => <button className={filter === item.id ? 'asset-filter active' : 'asset-filter'} key={item.id} type="button" aria-pressed={filter === item.id} onClick={() => setFilter(item.id)}><Icon name={item.icon} size={15} /><span>{item.label}</span><b>{counts[item.id] || 0}</b></button>)}
        </nav>
        <div className="asset-list" aria-label="画布资产列表">
          {visibleNodes.length ? visibleNodes.map((node) => (
            <button className={`asset-list-item${selectedId === node.id ? ' active' : ''}`} type="button" key={node.id} onClick={() => onSelect(node.id)} title="定位到画布组件">
              <span className={`asset-list-icon asset-list-${categoryForNode({ data: storyData(node) }) || storyData(node).nodeType}`}><AssetIcon node={node} /></span>
              <span className="asset-list-copy"><strong>{storyData(node).label || '未命名组件'}</strong><small>{categoryLabelForNode({ data: storyData(node) })}{storyData(node).panel_id ? ` · ${storyData(node).panel_id}` : ''}</small></span>
              <Icon name="chevronRight" size={14} className="asset-list-arrow" />
            </button>
          )) : <p className="asset-empty">没有匹配的资产<br /><small>拖入组件后会出现在这里</small></p>}
        </div>
        <div className="palette-divider" />
        <div className="palette-tool-title"><span>添加到画布</span><small>点击或拖入</small></div>
      </>}
      <div className="palette-items">
        {ITEMS.map((item) => (
          <button
            className={`palette-item palette-${item.type}`}
            key={item.type}
            type="button"
            draggable
            onDragStart={(event) => dragStart(event, item.type)}
            onClick={() => onAdd(item.type)}
            title={`${item.label}：${item.hint}`}
            aria-label={`添加${item.label}`}
          >
            <span className="palette-icon"><Icon name={item.icon} /></span>
            {!collapsed && <span>{item.label}</span>}
          </button>
        ))}
      </div>
      {!collapsed && <div className="palette-foot"><span>{mediaCount} 份媒体</span><span>保存在本机</span></div>}
    </aside>
  );
}

function AssetIcon({ node }: { node: FlowNode }) {
  const data = node.data as unknown as StoryNodeData;
  const asset = data.latestSuccessfulRun?.outputs?.[0] || data.asset;
  if (asset && (asset.kind.startsWith('image') || /\.(png|jpe?g|webp|gif)$/i.test(asset.path))) return <img src={mediaUrl(asset.path)} alt="" loading="lazy" />;
  return <Icon name={FILTERS.find((item) => item.id && item.id === categoryForNode({ data }))?.icon || (data.nodeType === 'asset' ? 'asset' : 'document')} size={18} />;
}
