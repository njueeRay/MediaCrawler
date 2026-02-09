## 概要
本项目提供两类 RESTful API：公共 API（/api/public/*）供第三方使用，多数无需认证；内部 API（/api/web/*）供前端调用，需 auth-key 认证。请求格式为 HTTP GET/POST，参数通过 query 或 body 传递；响应统一包含 base_resp（ret/err_msg）与业务数据。公共 API 支持搜索公众号、获取文章列表、下载文章内容（支持 html/markdown/text）、获取作者信息等 [1](#3-0) 。

## 公共 API 请求与响应格式

### 1. 搜索公众号（/api/public/v1/account）
- 请求：GET，参数 keyword（必填）、begin、size [2](#3-1) 。
- 响应：base_resp、total、list（含 fakeid、nickname、round_head_img 等） [3](#3-2) 。

### 2. 获取文章列表（/api/public/v1/article）
- 请求：GET，参数 fakeid（必填）、begin、size [4](#3-3) 。
- 响应：base_resp、articles（含 aid、title、cover、link、author_name 等） [5](#3-4) 。

### 3. 下载文章内容（/api/public/v1/download）
- 请求：GET，参数 url（必填，需 URL 编码）、format（可选，支持 html/markdown/text） [6](#3-5) 。
- 响应：直接返回对应格式的内容与 Content-Type，或错误时返回 base_resp [7](#3-6) 。

### 4. 获取作者信息（/api/public/beta/authorinfo）
- 请求：GET，参数 fakeid（必填） [8](#3-7) 。
- 响应：base_resp、identity_name、is_verify、original_article_count [9](#3-8) 。

## 内部 API 认证与响应
- 认证方式：通过 X-Auth-Key 请求头或 auth-key Cookie 传递 auth-key [10](#3-9) 。
- 响应结构：统一包含 base.ret（0 成功，200003 会话过期，其他为错误）与 base.err_msg，业务数据随端点变化 [11](#3-10) 。

## 返回数据示例
公共 API 成功响应示例见 config/public-apis.ts 的 responseSample 字段，错误统一返回 { base_resp: { ret: -1, err_msg: "..." } } [12](#3-11) 。

## Notes
- 公共 API 多数无需密钥，但部分 beta 接口可接受可选 key 参数 [13](#3-12) 。
- 内部 API 用于前端操作，需先登录获取 auth-key [14](#3-13) 。
- 完整 API 文档可在项目内 /dashboard/api 页面交互查看 [15](#3-14) 。

Wiki pages you might want to explore:
- [Backend APIs (wechat-article/wechat-article-exporter)](/wiki/wechat-article/wechat-article-exporter#7)
- [Public API Endpoints (wechat-article/wechat-article-exporter)](/wiki/wechat-article/wechat-article-exporter#7.1)
- [Internal API Endpoints (wechat-article/wechat-article-exporter)](/wiki/wechat-article/wechat-article-exporter#7.2)

### Citations

**File:** config/public-apis.ts (L1-427)
```typescript
// public api
export const apis = [
  {
    name: '根据关键字搜索公众号',
    description: '根据公众号名称或关键字查询公众号列表。',
    url: '/api/public/v1/account',
    method: 'GET',
    params: [
      {
        label: '关键字',
        name: 'keyword',
        location: 'query',
        required: true,
        default: 'N/A',
        type: 'String',
        remark: '',
      },
      {
        label: '起始索引',
        name: 'begin',
        location: 'query',
        required: false,
        default: '0',
        type: 'Int',
        remark: '下标从0开始，不能为负',
      },
      {
        label: '返回条数',
        name: 'size',
        location: 'query',
        required: false,
        default: '5',
        type: 'Int',
        remark: '最大不得超过20',
      },
    ],
    responseSample: {
      base_resp: {
        ret: 0,
        err_msg: 'ok',
      },
      total: 2,
      list: [
        {
          fakeid: 'MzA3NzAyMzMyMA==',
          nickname: '铁路12306',
          alias: 'CRTT12306',
          round_head_img:
            'http://mmbiz.qpic.cn/mmbiz_png/1774PicJv1ocOBxUD1Kh8gqx6HmD105nGnCg4j84mw4gxtmgsbgaVbiaOq6fCgVpHjwjELnMTGV8IR6kq7XJNkdw/0?wx_fmt=png',
          service_type: 2,
          signature: '欢迎您关注铁路12306，我们竭诚为您提供火车票、畅行会员、列车餐饮、酒店预订、旅游等服务。',
          verify_status: 2,
        },
        {
          fakeid: 'MjM5NTM0Mzg0MA==',
          nickname: '12321受理中心',
          alias: 'zg12321jbzx',
          round_head_img:
            'http://mmbiz.qpic.cn/mmbiz_png/b6geF0mDiaH4E82KiagmLc2DiaPrvzbSaELEde0xfZXrmcUzdBjK2G0ME4U1rwCvk0ZmtUsOncAkpnYTNoyDfhx6A/0?wx_fmt=png',
          service_type: 2,
          signature: ' ',
          verify_status: 2,
        },
      ],
    },
  },
  {
    name: '根据文章链接搜索公众号',
    description: '根据公众号文章链接查询公众号。',
    url: '/api/public/v1/accountbyurl',
    method: 'GET',
    params: [
      {
        label: '文章链接',
        name: 'url',
        location: 'query',
        required: true,
        default: 'N/A',
        type: 'String',
        remark: '',
      },
    ],
    responseSample: {
      base_resp: {
        ret: 0,
        err_msg: 'ok',
      },
      list: [
        {
          fakeid: 'MzA3NTg4MDUzNQ==',
          nickname: '肖小跑',
          alias: '',
          round_head_img:
            'http://mmbiz.qpic.cn/mmbiz_png/TEq4bibSxYafowUFshRICokwNXiaUB9zCX3vicx8FuhTCGibTa478JI72bkbpa89ssAqEFm2ib1S1LB0FEjHycjib8OA/0?wx_fmt=png',
          service_type: 1,
          signature:
            '金融世界不讲道理的时候，向文史哲求救，大概率“叮”的一下就扣上了。因为在这里，您才能再次看到“人”：人的情绪，人的荒诞，人的大举动小动作。这里有世界最本质的规律。',
          verify_status: 0,
        },
      ],
      total: 1,
    },
  },
  {
    name: '获取文章列表',
    description: '获取公众号的历史文章列表',
    url: '/api/public/v1/article',
    method: 'GET',
    params: [
      {
        label: '公众号id',
        name: 'fakeid',
        location: 'query',
        required: true,
        default: 'N/A',
        type: 'String',
        remark: '',
      },
      {
        label: '起始索引',
        name: 'begin',
        location: 'query',
        required: false,
        default: '0',
        type: 'Int',
        remark: '下标从0开始，不能为负',
      },
      {
        label: '返回消息条数',
        name: 'size',
        location: 'query',
        required: false,
        default: '5',
        type: 'Int',
        remark: '最大不得超过20，一条消息可能会包含多篇文章',
      },
    ],
    responseSample: {
      base_resp: {
        err_msg: 'ok',
        ret: 0,
      },
      articles: [
        {
          aid: '2247503214_1',
          title: '我用ChatGPT AI Agent做了一个堆栈模拟器！',
          cover:
            'https://mmbiz.qpic.cn/mmbiz_jpg/jXQDbLkGBYXdb3LgmxYMRclBo2wibeyib4MFwhyI3mWQ6dwZOKvCXWibCXVLnr9e0rTUf9IzZn3LPDQBlEwXzyJ8Q/0?wx_fmt=jpeg',
          link: 'https://mp.weixin.qq.com/s/wZxawrdSdSUAAZc89XuhWg',
          digest: '',
          update_time: 1753666492,
          appmsgid: 2247503214,
          itemidx: 1,
          item_show_type: 0,
          author_name: '轩辕之风',
          tagid: [],
          create_time: 1753666493,
          is_pay_subscribe: 0,
          has_red_packet_cover: 0,
          album_id: '3457885223537541125',
          checking: 0,
          media_duration: '0:00',
          mediaapi_publish_status: 0,
          copyright_type: 1,
          appmsg_album_infos: [
            {
              id: '3457885223537541125',
              title: '人工智能',
              album_id: 3457885223537541000,
              appmsg_album_infos: [],
              tagSource: 0,
            },
          ],
          pay_album_info: {
            appmsg_album_infos: [],
          },
          is_deleted: false,
          ban_flag: 0,
          pic_cdn_url_235_1:
            'https://mmbiz.qpic.cn/mmbiz_jpg/jXQDbLkGBYXdb3LgmxYMRclBo2wibeyib4V7nwzMbwLYKbgFSSbnQt0rUmdz1XcSE33YFzfqpVrYNKD8DagbnPRw/0?wx_fmt=jpeg',
          pic_cdn_url_16_9: '',
          pic_cdn_url_3_4: '',
          pic_cdn_url_1_1:
            'https://mmbiz.qpic.cn/mmbiz_jpg/jXQDbLkGBYXdb3LgmxYMRclBo2wibeyib4MFwhyI3mWQ6dwZOKvCXWibCXVLnr9e0rTUf9IzZn3LPDQBlEwXzyJ8Q/0?wx_fmt=jpeg',
          cover_img:
            'http://mmbiz.qpic.cn/mmbiz_jpg/jXQDbLkGBYXdb3LgmxYMRclBo2wibeyib4MFwhyI3mWQ6dwZOKvCXWibCXVLnr9e0rTUf9IzZn3LPDQBlEwXzyJ8Q/0?wx_fmt=jpeg',
          cover_img_theme_color: {
            r: 255,
            g: 255,
            b: 255,
          },
          line_info: {
            use_line: 1,
            line_count: 0,
            is_appmsg_flag: 1,
            is_use_flag: 0,
          },
          copyright_stat: 1,
          is_rumor_refutation: 0,
          multi_picture_cover: 0,
          share_imageinfo: [],
        },
        {
          aid: '2247503179_1',
          title: '抖音C++安全开发面试题，已阵亡！',
          cover:
            'https://mmbiz.qpic.cn/mmbiz_jpg/jXQDbLkGBYUYIgV3fNdQyKIysEER6tQZCpgfTrYwfKX67eRWicg9TIciadwXJF9QMhUiaLaR4iabdwdiaib7FmWY62eg/0?wx_fmt=jpeg',
          link: 'https://mp.weixin.qq.com/s/eFsIOWDXfs9DbcNmr2vtjQ',
          digest: '',
          update_time: 1753230604,
          appmsgid: 2247503179,
          itemidx: 1,
          item_show_type: 0,
          author_name: '轩辕之风',
          tagid: [],
          create_time: 1753230605,
          is_pay_subscribe: 0,
          has_red_packet_cover: 0,
          album_id: '3560766261049098241',
          checking: 0,
          media_duration: '0:00',
          mediaapi_publish_status: 0,
          copyright_type: 1,
          appmsg_album_infos: [
            {
              id: '3560766261049098241',
              title: 'C/C++',
              album_id: 3560766261049098000,
              appmsg_album_infos: [],
              tagSource: 0,
            },
          ],
          pay_album_info: {
            appmsg_album_infos: [],
          },
          is_deleted: false,
          ban_flag: 0,
          pic_cdn_url_235_1:
            'https://mmbiz.qpic.cn/mmbiz_jpg/jXQDbLkGBYUYIgV3fNdQyKIysEER6tQZuuUaqiazzPPoUFqFWicZ7bsW8z6g9FhkbibyqRtfZwRAkFHhPIydWpLnQ/0?wx_fmt=jpeg',
          pic_cdn_url_16_9: '',
          pic_cdn_url_3_4: '',
          pic_cdn_url_1_1:
            'https://mmbiz.qpic.cn/mmbiz_jpg/jXQDbLkGBYUYIgV3fNdQyKIysEER6tQZCpgfTrYwfKX67eRWicg9TIciadwXJF9QMhUiaLaR4iabdwdiaib7FmWY62eg/0?wx_fmt=jpeg',
          line_info: {
            use_line: 1,
            line_count: 0,
            is_appmsg_flag: 1,
            is_use_flag: 0,
          },
          copyright_stat: 1,
          is_rumor_refutation: 0,
          multi_picture_cover: 0,
          share_imageinfo: [],
        },
      ],
    },
  },
  {
    name: '获取文章内容',
    description: '获取文章内容，支持 html / markdown / text 格式',
    url: '/api/public/v1/download',
    method: 'GET',
    params: [
      {
        label: '文章链接',
        name: 'url',
        location: 'query',
        required: true,
        default: 'N/A',
        type: 'String',
        remark: '需经过url编码',
      },
      {
        label: '输出格式',
        name: 'format',
        location: 'query',
        required: false,
        default: 'html',
        type: 'String',
        remark: '支持 html / markdown / text 格式',
      },
    ],
    responseSample: {},
    remark: '此接口不需要 API 密钥',
  },
  {
    name: '查询公众号主体信息 (beta)',
    description: '根据公众号的 fakeid 查询主体信息',
    url: '/api/public/beta/authorinfo',
    method: 'GET',
    params: [
      {
        label: '公众号id',
        name: 'fakeid',
        location: 'query',
        required: true,
        default: 'N/A',
        type: 'String',
        remark: '',
      },
    ],
    responseSample: {
      base_resp: {
        exportkey_token: '',
        ret: 0,
      },
      identity_name: '上海市总工会',
      is_verify: 2,
      original_article_count: 262,
    },
    remark: '此接口不需要 API 密钥',
  },
  {
    name: '查询公众号主体信息 (beta)',
    description: '根据公众号的 fakeid 查询主体信息',
    url: '/api/public/beta/aboutbiz',
    method: 'GET',
    params: [
      {
        label: '公众号id',
        name: 'fakeid',
        location: 'query',
        required: true,
        default: 'N/A',
        type: 'String',
        remark: '',
      },
      {
        label: '密钥',
        name: 'key',
        location: 'query',
        required: false,
        default: 'N/A',
        type: 'String',
        remark: '微信抓包获取的x-wechat-key参数',
      },
    ],
    responseSample: {
      base_resp: {
        ret: 0,
      },
      data: {
        intro: '做一个有存在意义的账号~这里是上海市总工会，欢迎回家！',
        wechat: 'shengongshewx',
        type: '其他组织',
        org: '上海市总工会',
        auth_3rd_list: [
          {
            principal: '秀米',
            userName: 'gh_d483129a0f29@app',
            appId: 'wx19e904724550a41f',
            relativeURL:
              'pages/profile/index?enterpriseOpenId=sq_o0CFMs_h0aKah0GsYaZZ3akyF8yo&amp;from=profile&amp;fromAppId=wx63d70210fcc108fd&amp;componentAppId=wx7d88eb47efa1e610',
            category: [
              {
                id: 7,
                name: '群发与通知',
                desc: '基于该权限可帮助公众号进行群发消息、文章管理以及发送模板消息',
              },
              {
                id: 11,
                name: '素材管理',
                desc: '基于该权限可帮助公众号管理图文等多媒体素材以及多媒体文件管理',
              },
            ],
          },
          {
            principal: '壹伴',
            userName: 'gh_d483129a0f29@app',
            appId: 'wx19e904724550a41f',
            relativeURL:
              'pages/profile/index?enterpriseOpenId=sq_omefmt3a0XFwUA1PfscJj7_n9fak&amp;from=profile&amp;fromAppId=wx63d70210fcc108fd&amp;componentAppId=wx3f5f5ddf688562c0',
            category: [
              {
                id: 1,
                name: '消息管理',
                desc: '基于该权限可帮助公众号接收用户消息，进行人工客服回复或自动回复',
              },
              {
                id: 2,
                name: '用户管理',
                desc: '帮助公众号获取用户信息，进行用户管理',
              },
              {
                id: 3,
                name: '公众号账号信息服务',
                desc: '基于该权限可帮助公众号设置及展示公众号信息、配置账号信息、生成带参二维码并配置跳转小程序等账号维度的功能',
              },
              {
                id: 4,
                name: '网页服务',
                desc: '基于该权限可帮助公众实现H5网页服务',
              },
              {
                id: 6,
                name: '微信多客服',
                desc: '基于该权限可帮助公众号使用微信多客服功能',
              },
              {
                id: 7,
                name: '群发与通知',
                desc: '基于该权限可帮助公众号进行群发消息、文章管理以及发送模板消息',
              },
              {
                id: 11,
                name: '素材管理',
                desc: '基于该权限可帮助公众号管理图文等多媒体素材以及多媒体文件管理',
              },
              {
                id: 15,
                name: '自定义菜单管理',
                desc: '帮助公众号使用自定义菜单',
              },
            ],
          },
        ],
        ip_wording: {
          countryName: '中国',
          countryId: '156',
          provinceName: '上海',
          provinceId: '',
          cityName: '',
          cityId: '',
        },
      },
    },
    remark: '此接口不需要 API 密钥',
```

**File:** server/api/public/v1/download.get.ts (L11-40)
```typescript
export default defineEventHandler(async event => {
  const query = getQuery<SearchBizQuery>(event);
  if (!query.url) {
    return {
      base_resp: {
        ret: -1,
        err_msg: 'url不能为空',
      },
    };
  }

  const url = decodeURIComponent(query.url.trim());
  if (!urlIsValidMpArticle(url)) {
    return {
      base_resp: {
        ret: -1,
        err_msg: 'url不合法',
      },
    };
  }

  const format: string = (query.format || 'html').toLowerCase();
  if (!['html', 'markdown', 'text'].includes(format)) {
    return {
      base_resp: {
        ret: -1,
        err_msg: '不支持的format',
      },
    };
  }
```

**File:** server/api/public/v1/download.get.ts (L50-74)
```typescript
  switch (format) {
    case 'html':
      return new Response(normalizeHtml(rawHtml, 'html'), {
        status: 200,
        headers: {
          'Content-Type': 'text/html; charset=UTF-8',
        },
      });
    case 'text':
      return new Response(normalizeHtml(rawHtml, 'text'), {
        status: 200,
        headers: {
          'Content-Type': 'text/plain; charset=UTF-8',
        },
      });
    case 'markdown':
      return new Response(new TurndownService().turndown(normalizeHtml(rawHtml, 'html')), {
        status: 200,
        headers: {
          'Content-Type': 'text/markdown; charset=UTF-8',
        },
      });
    default:
      throw new Error(`Unknown format ${format}`);
  }
```

**File:** components/api/Summary.vue (L56-59)
```vue
            <p>以下所有 <code>API</code> 如无特殊说明，均需要携带密钥进行调用。密钥可通过以下两种方式传输：</p>
            <p>a. 通过自定义请求头 <code class="text-rose-500 font-medium font-mono">X-Auth-Key</code></p>
            <p>b. 通过 name 为 <code class="text-rose-500 font-medium font-mono">auth-key</code> 的 Cookie</p>
          </li>
```

**File:** apis/index.ts (L59-71)
```typescript
    }

    const articles = publish_list.flatMap(item => {
      const publish_info: PublishInfo = JSON.parse(item.publish_info);
      return publish_info.appmsgex;
    });
    return [articles, isCompleted, publish_page.total_count];
  } else if (resp.base_resp.ret === 200003) {
    loginAccount.value = null;
    throw new Error('session expired');
  } else {
    throw new Error(`${resp.base_resp.ret}:${resp.base_resp.err_msg}`);
  }
```

**File:** server/api/web/login/bizlogin.post.ts (L22-36)
```typescript
  const response: Response = await proxyMpRequest({
    event: event,
    method: 'POST',
    endpoint: 'https://mp.weixin.qq.com/cgi-bin/bizlogin',
    query: {
      action: 'login',
    },
    body: payload,
    cookie: cookie,
    action: 'login', // 有这个标志就会把微信原始响应中的所有 set-cookie 存储在 CookieStore 中，并返回给客户端一个唯一的cookie: auth-key=xxx
  });

  // 从响应中取出唯一的 set-cookie (即上一步 `action=login` 标志所设置的 auth-key=xxx)
  const authKey = getCookieFromResponse('auth-key', response);
  if (!authKey) {
```

**File:** components/api/Document.vue (L31-90)
```vue
<template>
  <div class="space-y-5">
    <h2 class="flex items-center space-x-3 text-2xl font-semibold font-serif py-2">
      <span>{{ index }}. {{ name }}</span>
      <ApiDebugModal :initial-selected="name" />
    </h2>

    <div>
      <p class="font-semibold mb-2">简要描述</p>
      <p class="font-serif">{{ description }}</p>
    </div>
    <div v-if="remark">
      <p class="font-semibold mb-2">备注:</p>
      <p class="text-rose-500">{{ remark }}</p>
    </div>
    <div>
      <p class="font-semibold mb-2">请求URL:</p>
      <p class="font-mono border p-2 rounded-md">
        <span class="text-gray-400">{{ host }}</span>
        <span class="font-semibold">{{ url }}</span>
      </p>
    </div>
    <div>
      <p class="font-semibold mb-2">请求方式:</p>
      <p class="font-mono border p-2 rounded-md">{{ method }}</p>
    </div>
    <div>
      <p class="font-semibold mb-2">参数:</p>
      <div class="border rounded-md overflow-hidden">
        <table class="font-mono">
          <thead>
            <tr>
              <th>参数名</th>
              <th>参数位置</th>
              <th>强制</th>
              <th>默认值</th>
              <th>类型</th>
              <th>说明</th>
              <th>备注</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in params" :key="p.name">
              <td>{{ p.name }}</td>
              <td>{{ p.location }}</td>
              <td>{{ p.required ? '是' : '否' }}</td>
              <td>{{ p.default }}</td>
              <td>{{ p.type }}</td>
              <td>{{ p.label }}</td>
              <td>{{ p.remark }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    <div>
      <p class="font-semibold flex items-center mb-2">
        <span class="mr-3">返回示例:</span>
        <UToggle v-model="open" color="blue" on-icon="i-heroicons:eye" off-icon="i-heroicons:eye-slash" />
      </p>
```
