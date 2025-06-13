import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc } from './_plugin-vue_export-helper-pcqpp-6-.js';

const {toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,resolveComponent:_resolveComponent,withCtx:_withCtx,createVNode:_createVNode,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createElementVNode:_createElementVNode,renderList:_renderList,Fragment:_Fragment,createElementBlock:_createElementBlock} = await importShared('vue');


const _hoisted_1 = { class: "plugin-page" };
const _hoisted_2 = { key: 2 };
const _hoisted_3 = { class: "text-h4 font-weight-bold" };
const _hoisted_4 = { class: "text-h4 font-weight-bold text-success" };
const _hoisted_5 = { class: "text-h4 font-weight-bold text-warning" };
const _hoisted_6 = { class: "text-h4 font-weight-bold text-info" };
const _hoisted_7 = {
  key: 0,
  class: "mt-4"
};
const _hoisted_8 = {
  key: 1,
  class: "mt-4"
};
const _hoisted_9 = { class: "d-flex align-center" };
const _hoisted_10 = { class: "font-weight-medium" };
const _hoisted_11 = { class: "text-caption text-secondary" };
const _hoisted_12 = { class: "mt-4 text-subtitle-2" };

const {ref,onMounted,computed} = await importShared('vue');


// 接收初始配置

const _sfc_main = {
  __name: 'Page',
  props: {
  model: {
    type: Object,
    default: () => ({
      title: '爬虫详情',
      stats: {
        total: 0,
        enabled: 0,
        disabled: 0,
        tags: []
      },
      recentItems: []
    }),
  },
  api: {
    type: Object,
    default: () => {},
  },
},
  emits: ['action', 'switch', 'close'],
  setup(__props, { emit: __emit }) {

const props = __props;

// 组件状态
const loading = ref(true);
const error = ref(null);
const status = ref('running');
const lastUpdated = ref('');

// 计算属性
const stats = computed(() => props.model.stats);
const recentItems = computed(() => props.model.recentItems);

// 自定义事件，用于通知主应用刷新数据
const emit = __emit;

// 获取状态图标
function getItemIcon(type) {
  const icons = {
    'movie': 'mdi-movie',
    'tv': 'mdi-television-classic',
    'download': 'mdi-download',
    'error': 'mdi-alert-circle',
    'success': 'mdi-check-circle',
  };
  return icons[type] || 'mdi-information'
}

// 获取状态颜色
function getItemColor(type) {
  const colors = {
    'movie': 'blue',
    'tv': 'green',
    'download': 'purple',
    'error': 'red',
    'success': 'success',
  };
  return colors[type] || 'grey'
}

// 获取和刷新数据
async function refreshData() {
  loading.value = true;
  error.value = null;

  try {
    // 获取爬虫状态
    const result = await props.api.get('plugin/ExtendSpider/status');
    if (result) {
      props.model.stats = {
        total: result.total || 0,
        enabled: result.enabled || 0,
        disabled: result.disabled || 0,
        tags: result.tags || []
      };
      status.value = result.status || 'running';
      lastUpdated.value = new Date().toLocaleString();
    }

    // 获取最近记录
    props.model.recentItems = await props.api.get('plugin/ExtendSpider/history') || [];
  } catch (err) {
    console.error('获取数据失败:', err);
    error.value = err.message || '获取数据失败';
  } finally {
    loading.value = false;
    // 通知主应用组件已更新
    emit('action');
  }
}

// 通知主应用切换到配置页面
function notifySwitch() {
  emit('switch');
}

// 通知主应用关闭组件
function notifyClose() {
  emit('close');
}

// 组件挂载时加载数据
onMounted(() => {
  refreshData();
});

return (_ctx, _cache) => {
  const _component_v_card_title = _resolveComponent("v-card-title");
  const _component_v_icon = _resolveComponent("v-icon");
  const _component_v_btn = _resolveComponent("v-btn");
  const _component_v_card_item = _resolveComponent("v-card-item");
  const _component_v_alert = _resolveComponent("v-alert");
  const _component_v_skeleton_loader = _resolveComponent("v-skeleton-loader");
  const _component_v_card_text = _resolveComponent("v-card-text");
  const _component_v_card = _resolveComponent("v-card");
  const _component_v_col = _resolveComponent("v-col");
  const _component_v_row = _resolveComponent("v-row");
  const _component_v_chip = _resolveComponent("v-chip");
  const _component_v_chip_group = _resolveComponent("v-chip-group");
  const _component_v_timeline_item = _resolveComponent("v-timeline-item");
  const _component_v_timeline = _resolveComponent("v-timeline");
  const _component_v_spacer = _resolveComponent("v-spacer");
  const _component_v_card_actions = _resolveComponent("v-card-actions");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createVNode(_component_v_card, null, {
      default: _withCtx(() => [
        _createVNode(_component_v_card_item, null, {
          append: _withCtx(() => [
            _createVNode(_component_v_btn, {
              icon: "",
              color: "primary",
              variant: "text",
              onClick: notifyClose
            }, {
              default: _withCtx(() => [
                _createVNode(_component_v_icon, { left: "" }, {
                  default: _withCtx(() => _cache[0] || (_cache[0] = [
                    _createTextVNode("mdi-close")
                  ])),
                  _: 1
                })
              ]),
              _: 1
            })
          ]),
          default: _withCtx(() => [
            _createVNode(_component_v_card_title, null, {
              default: _withCtx(() => [
                _createTextVNode(_toDisplayString(__props.model.title), 1)
              ]),
              _: 1
            })
          ]),
          _: 1
        }),
        _createVNode(_component_v_card_text, null, {
          default: _withCtx(() => [
            (error.value)
              ? (_openBlock(), _createBlock(_component_v_alert, {
                  key: 0,
                  type: "error",
                  class: "mb-4"
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(error.value), 1)
                  ]),
                  _: 1
                }))
              : _createCommentVNode("", true),
            (loading.value)
              ? (_openBlock(), _createBlock(_component_v_skeleton_loader, {
                  key: 1,
                  type: "card"
                }))
              : (_openBlock(), _createElementBlock("div", _hoisted_2, [
                  _createVNode(_component_v_row, null, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_col, {
                        cols: "12",
                        sm: "6",
                        md: "3"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_card, {
                            variant: "outlined",
                            class: "text-center"
                          }, {
                            default: _withCtx(() => [
                              _createVNode(_component_v_card_text, null, {
                                default: _withCtx(() => [
                                  _createElementVNode("div", _hoisted_3, _toDisplayString(stats.value.total), 1),
                                  _cache[1] || (_cache[1] = _createElementVNode("div", { class: "text-subtitle-1" }, "爬虫总数", -1))
                                ]),
                                _: 1
                              })
                            ]),
                            _: 1
                          })
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, {
                        cols: "12",
                        sm: "6",
                        md: "3"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_card, {
                            variant: "outlined",
                            class: "text-center"
                          }, {
                            default: _withCtx(() => [
                              _createVNode(_component_v_card_text, null, {
                                default: _withCtx(() => [
                                  _createElementVNode("div", _hoisted_4, _toDisplayString(stats.value.enabled), 1),
                                  _cache[2] || (_cache[2] = _createElementVNode("div", { class: "text-subtitle-1" }, "已启用", -1))
                                ]),
                                _: 1
                              })
                            ]),
                            _: 1
                          })
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, {
                        cols: "12",
                        sm: "6",
                        md: "3"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_card, {
                            variant: "outlined",
                            class: "text-center"
                          }, {
                            default: _withCtx(() => [
                              _createVNode(_component_v_card_text, null, {
                                default: _withCtx(() => [
                                  _createElementVNode("div", _hoisted_5, _toDisplayString(stats.value.disabled), 1),
                                  _cache[3] || (_cache[3] = _createElementVNode("div", { class: "text-subtitle-1" }, "已禁用", -1))
                                ]),
                                _: 1
                              })
                            ]),
                            _: 1
                          })
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, {
                        cols: "12",
                        sm: "6",
                        md: "3"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_card, {
                            variant: "outlined",
                            class: "text-center"
                          }, {
                            default: _withCtx(() => [
                              _createVNode(_component_v_card_text, null, {
                                default: _withCtx(() => [
                                  _createElementVNode("div", _hoisted_6, _toDisplayString(stats.value.tags.length), 1),
                                  _cache[4] || (_cache[4] = _createElementVNode("div", { class: "text-subtitle-1" }, "标签数量", -1))
                                ]),
                                _: 1
                              })
                            ]),
                            _: 1
                          })
                        ]),
                        _: 1
                      })
                    ]),
                    _: 1
                  }),
                  (stats.value.tags.length)
                    ? (_openBlock(), _createElementBlock("div", _hoisted_7, [
                        _cache[5] || (_cache[5] = _createElementVNode("div", { class: "text-h6 mb-2" }, "标签列表", -1)),
                        _createVNode(_component_v_chip_group, null, {
                          default: _withCtx(() => [
                            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(stats.value.tags, (tag) => {
                              return (_openBlock(), _createBlock(_component_v_chip, {
                                key: tag,
                                color: "primary",
                                variant: "outlined",
                                class: "ma-1"
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(tag), 1)
                                ]),
                                _: 2
                              }, 1024))
                            }), 128))
                          ]),
                          _: 1
                        })
                      ]))
                    : _createCommentVNode("", true),
                  (recentItems.value && recentItems.value.length)
                    ? (_openBlock(), _createElementBlock("div", _hoisted_8, [
                        _cache[6] || (_cache[6] = _createElementVNode("div", { class: "text-h6 mb-2" }, "最近记录", -1)),
                        _createVNode(_component_v_timeline, { density: "compact" }, {
                          default: _withCtx(() => [
                            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(recentItems.value, (item, index) => {
                              return (_openBlock(), _createBlock(_component_v_timeline_item, {
                                key: index,
                                "dot-color": getItemColor(item.type),
                                size: "small"
                              }, {
                                default: _withCtx(() => [
                                  _createElementVNode("div", _hoisted_9, [
                                    _createVNode(_component_v_icon, {
                                      color: getItemColor(item.type),
                                      size: "small",
                                      class: "mr-2"
                                    }, {
                                      default: _withCtx(() => [
                                        _createTextVNode(_toDisplayString(getItemIcon(item.type)), 1)
                                      ]),
                                      _: 2
                                    }, 1032, ["color"]),
                                    _createElementVNode("span", _hoisted_10, _toDisplayString(item.title), 1)
                                  ]),
                                  _createElementVNode("div", _hoisted_11, _toDisplayString(item.time), 1)
                                ]),
                                _: 2
                              }, 1032, ["dot-color"]))
                            }), 128))
                          ]),
                          _: 1
                        })
                      ]))
                    : _createCommentVNode("", true),
                  _createElementVNode("div", _hoisted_12, [
                    _createElementVNode("div", null, [
                      _cache[7] || (_cache[7] = _createElementVNode("strong", null, "状态:", -1)),
                      _createVNode(_component_v_chip, {
                        size: "small",
                        color: status.value === 'running' ? 'success' : 'warning'
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode(_toDisplayString(status.value), 1)
                        ]),
                        _: 1
                      }, 8, ["color"])
                    ]),
                    _createElementVNode("div", null, [
                      _cache[8] || (_cache[8] = _createElementVNode("strong", null, "最后更新:", -1)),
                      _createTextVNode(" " + _toDisplayString(lastUpdated.value), 1)
                    ])
                  ])
                ]))
          ]),
          _: 1
        }),
        _createVNode(_component_v_card_actions, null, {
          default: _withCtx(() => [
            _createVNode(_component_v_btn, {
              color: "primary",
              onClick: refreshData,
              loading: loading.value
            }, {
              default: _withCtx(() => [
                _createVNode(_component_v_icon, { left: "" }, {
                  default: _withCtx(() => _cache[9] || (_cache[9] = [
                    _createTextVNode("mdi-refresh")
                  ])),
                  _: 1
                }),
                _cache[10] || (_cache[10] = _createTextVNode(" 刷新数据 "))
              ]),
              _: 1
            }, 8, ["loading"]),
            _createVNode(_component_v_spacer),
            _createVNode(_component_v_btn, {
              color: "primary",
              onClick: notifySwitch
            }, {
              default: _withCtx(() => [
                _createVNode(_component_v_icon, { left: "" }, {
                  default: _withCtx(() => _cache[11] || (_cache[11] = [
                    _createTextVNode("mdi-cog")
                  ])),
                  _: 1
                }),
                _cache[12] || (_cache[12] = _createTextVNode(" 配置 "))
              ]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    })
  ]))
}
}

};
const PageComponent = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-eb29d8ce"]]);

export { PageComponent as default };
