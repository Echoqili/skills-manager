(function() {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var warning = '#f59e0b';
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var bg2 = style.getPropertyValue('--bg2').trim();

  var chartSeverity = echarts.init(document.getElementById('chart-severity'), null, { renderer: 'svg' });
  chartSeverity.setOption({
    animation: false,
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, appendToBody: true },
    legend: { data: ['高', '中', '低'], textStyle: { color: muted }, bottom: 0 },
    grid: { left: '3%', right: '4%', bottom: '12%', top: '10%', containLabel: true },
    xAxis: {
      type: 'category',
      data: ['Skill 卡片/详情', '搜索与发现', '购物车与打包', '高级功能', '国际化'],
      axisLine: { lineStyle: { color: rule } },
      axisLabel: { color: muted, interval: 0, rotate: 20 }
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      splitLine: { lineStyle: { color: rule, type: 'dashed' } },
      axisLabel: { color: muted }
    },
    series: [
      {
        name: '高',
        type: 'bar',
        stack: 'total',
        data: [3, 0, 0, 0, 0],
        itemStyle: { color: accent2, borderRadius: [0, 0, 0, 0] }
      },
      {
        name: '中',
        type: 'bar',
        stack: 'total',
        data: [1, 2, 2, 0, 0],
        itemStyle: { color: warning }
      },
      {
        name: '低',
        type: 'bar',
        stack: 'total',
        data: [0, 0, 0, 2, 1],
        itemStyle: { color: accent, borderRadius: [4, 4, 0, 0] }
      }
    ]
  });

  window.addEventListener('resize', function() {
    chartSeverity.resize();
  });
})();
