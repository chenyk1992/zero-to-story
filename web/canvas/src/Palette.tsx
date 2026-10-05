import { useEffect, useMemo, useRef, useState } from 'react';
import type { FlowNode } from './types';
import { Icon, type IconName } from './Icon';
import { mediaUrl } from './api';
import { categoryForNode, categoryLabelForNode, isSectionNode, mediaCountForNode, nodeSearchText, type StoryNodeData, type StoryNodeType } from './workspace';

const ITEMS: Array<{ type: StoryNodeType; label: string; hint: string; icon: IconName }> = [
  { type: 'document', label: '文档', hint: '故事板或章节笔记', icon: 'document' },
  { type: 'section', label: '分区', hint: '组织场景、镜头与角色', icon: 'section' },
  { type: 'asset', label: '素材', hint: '图片、视频或音频', icon: 'asset' },
  { type: 'image', label: '图片', hint: '图片创作卡，选择可用生成方式', icon: 'image' },
  { type: 'video', label: '视频', hint: '视频创作卡，选择可用生成方式', icon: 'video' },
  { type: 'audio', label: '音频', hint: '选择音乐或语音生成方式，并填写对应输入', icon: 'audio' },
];

const FILTERS: Array<{ id: string; label: string; icon: IconName; title?: string }> = [
  { id: '', label: '全部', icon: 'grid' },
  { id: 'character', label: '角色参考', icon: 'character' },
  { id: 'storyboard', label: '故事板', icon: 'storyboard' },
  { id: 'board', label: '分镜板', title: '电影画面分镜板', icon: 'board' },
  { id: 'image', label: '图片', icon: 'image' },
  { id: 'video', label: '视频', icon: 'video' },
  { id: 'audio', label: '音频', icon: 'audio' },
  { id: 'document', label: '文档', icon: 'document' },
];

interface PaletteProps {
  nodes: FlowNode[];
  selectedId?: string;
  onAdd: (type: StoryNodeType) => void;
  onSelect: (nodeId: string) => void;
  collapsed?: boolean;
  onToggle?: () => void;
  searchRequest?: number;
}

export function Palette({ nodes, selectedId, onAdd, onSelect, collapsed = false, onToggle, searchRequest = 0 }: PaletteProps) {
  const [view, setView] = useState<'assets' | 'outline'>('assets');
  const [filter, setFilter] = useState('');
  const [search, setSearch] = useState('');
  const searchRef = useRef<HTMLInputElement>(null);
  const handledSearchRequest = useRef(0);
  const storyData = (node: FlowNode) => node.data as unknown as StoryNodeData;
  const assetNodes = useMemo(() => nodes.filter((node) => !isSectionNode(node)), [nodes]);
  const outlineNodes = useMemo(() => [...nodes.filter(isSectionNode), ...assetNodes], [nodes, assetNodes]);
  const counts = useMemo(() => FILTERS.reduce<Record<string, number>>((result, item) => {
    result[item.id] = item.id ? assetNodes.filter((node) => categoryForNode({ data: storyData(node) }) === item.id).length : assetNodes.length;
    return result;
  }, {}), [assetNodes]);
  const mediaCount = useMemo(() => assetNodes.reduce((count, node) => count + mediaCountForNode({ data: storyData(node) }), 0), [assetNodes]);
  const visibleNodes = useMemo(() => (view === 'outline' ? outlineNodes : assetNodes).filter((node) => {
    const matchesFilter = view === 'outline' || !filter || categoryForNode({ data: storyData(node) }) === filter;
    const matchesSearch = !search.trim() || nodeSearchText({ id: node.id, data: storyData(node) }).includes(search.trim().toLocaleLowerCase());
    return matchesFilter && matchesSearch;
  }), [view, outlineNodes, assetNodes, filter, search]);
  const hasFilters = Boolean(search.trim() || view === 'assets' && filter);

  useEffect(() => {
    if (collapsed || searchRequest <= handledSearchRequest.current) return;
    searchRef.current?.focus();
    handledSearchRequest.current = searchRequest;
  }, [collapsed, searchRequest]);

  const clearSearch = () => {
    setSearch('');
    searchRef.current?.focus();
  };

  const resetFilters = () => {
    setFilter('');
    clearSearch();
  };

  const dragStart = (event: React.DragEvent<HTMLButtonElement>, type: StoryNodeType) => {
    event.dataTransfer.effectAllowed = 'copy';
    event.dataTransfer.setData('application/x-canvas-node', type);
  };

  return (
    <aside className={`palette${collapsed ? ' palette-collapsed' : ''}`} aria-label="故事资产导航">
      <div className="palette-brand">{!collapsed && <strong>章节导航 <small>{view === 'outline' ? nodes.length : assetNodes.length}</small></strong>}<button className="palette-collapse" type="button" onClick={onToggle} title={collapsed ? '展开资产栏' : '收起资产栏'} aria-label={collapsed ? '展开资产栏' : '收起资产栏'}><Icon name="panelLeft" /></button></div>
      {!collapsed && <>
        <div className="palette-view-switch" role="group" aria-label="导航视图">
          <button className={`palette-view-button${view === 'assets' ? ' active' : ''}`} type="button" aria-pressed={view === 'assets'} onClick={() => setView('assets')}><Icon name="asset" size={15} /><span>素材</span></button>
          <button className={`palette-view-button${view === 'outline' ? ' active' : ''}`} type="button" aria-pressed={view === 'outline'} onClick={() => setView('outline')}><Icon name="layers" size={15} /><span>大纲</span></button>
        </div>
        <label className="asset-search"><Icon name="search" size={16} /><input ref={searchRef} value={search} onChange={(event) => setSearch(event.target.value)} placeholder={view === 'outline' ? '搜索分区、镜头、角色…' : '搜索角色、镜头…'} aria-label={view === 'outline' ? '搜索画布大纲' : '搜索章节资产'} />{search && <button type="button" onClick={clearSearch} aria-label="清除搜索"><Icon name="close" size={14} /></button>}</label>
        {view === 'assets' && <nav className="asset-filters" aria-label="资产分类">
          {FILTERS.map((item) => <button className={filter === item.id ? 'asset-filter active' : 'asset-filter'} key={item.id} type="button" title={item.title} aria-pressed={filter === item.id} onClick={() => setFilter(item.id)}><Icon name={item.icon} size={15} /><span>{item.label}</span><b>{counts[item.id] || 0}</b></button>)}
        </nav>}
        <div className="asset-list" aria-label={view === 'outline' ? '画布大纲列表' : '画布资产列表'}>
          {visibleNodes.length ? visibleNodes.map((node) => (
            <button className={`asset-list-item${isSectionNode(node) ? ' asset-list-section' : ''}${selectedId === node.id ? ' active' : ''}`} type="button" key={node.id} onClick={() => onSelect(node.id)} aria-current={selectedId === node.id ? 'true' : undefined} title={isSectionNode(node) ? '定位到画布分区' : '定位到画布组件'}>
              <span className={`asset-list-icon asset-list-${categoryForNode({ data: storyData(node) }) || storyData(node).nodeType}`}><AssetIcon node={node} /></span>
              <span className="asset-list-copy"><strong>{storyData(node).label || '未命名组件'}</strong><small>{categoryLabelForNode({ data: storyData(node) })}{storyData(node).panel_id ? ` · ${storyData(node).panel_id}` : ''}</small></span>
              <Icon name="chevronRight" size={14} className="asset-list-arrow" />
            </button>
          )) : <div className="asset-empty"><p>{hasFilters ? '没有匹配的组件' : view === 'outline' ? '大纲还是空的' : '还没有素材'}<br /><small>{hasFilters ? '试试其他关键词，或恢复全部组件' : '从下方添加组件，开始整理这一章'}</small></p>{hasFilters && <button className="asset-empty-reset" type="button" onClick={resetFilters}>重置筛选</button>}</div>}
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
  if (isSectionNode(node)) return <Icon name="section" size={18} />;
  const asset = data.latestSuccessfulRun?.outputs?.[0] || data.asset;
  if (asset && (asset.kind.startsWith('image') || /\.(png|jpe?g|webp|gif)$/i.test(asset.path))) return <img src={mediaUrl(asset.path)} alt="" loading="lazy" />;
  return <Icon name={FILTERS.find((item) => item.id && item.id === categoryForNode({ data }))?.icon || (data.nodeType === 'asset' ? 'asset' : 'document')} size={18} />;
}
