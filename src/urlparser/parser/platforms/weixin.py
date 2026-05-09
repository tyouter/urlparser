"""
微信公众号 (Weixin) 解析器
"""

from typing import Dict
from playwright.async_api import Page

from ..base import ArticleParser
from ..models import ParserConfig
from ..mixins.content_clean import ContentCleanMixin


_WEIXIN_REMOVE_SELECTORS = [
    '#js_pc_qr_code',
    '#js_share_guide',
    '#js_sponsor_ad_area',
    '#js_tags_preview_area',
    '#js_tags_area',
    '.reward_area',
    '.reward_area_box',
    '.read_more_area',
    '.rich_media_tool_area',
    '#js_reader_bottom_area',
    '#js_cmt_area',
    '#js_comment_area',
    '.comment_area',
    '#js_pc_toast',
    '#js_image_view',
    '.profile_card_wrap',
    '.rich_media_area_extra',
    '#js_tags_container',
    '.article-bottom-area',
    '.share_area',
    '.tips_global',
    '.weui-dialog',
    '.weui-mask',
    '.weui-toast',
    '#js_bottom_banner',
    '.bottom_banner_area',
    '#js_ad_area',
    '.rich_media_ad_switch',
    '.js_ad_container',
    '.js_ad_inner',
    '#js_tags_list',
    '.rich_media_tool',
    '#js_article_edit_area',
    '.original_area',
    '.copyright_area',
    '#js_author_name',
    '.profile_arrow_wrap',
    '.js_wx_tap_highlight',
    '#js_content_bottom_area',
    '.rich_media_content_primary_bottom',
    '#js_vote_area',
    '.vote_area',
    '.js_img_popup_area',
    '#js_img_popup',
    '.img_popup_area',
    '#js_pc_close_btn',
    '.pc_close_btn',
    '#js_next_article_area',
    '.next_article_area',
    '#js_chinese_suggest',
    '.chinese_suggest',
    '.js_appmsg_analysis',
    '.appmsg_analysis',
    '#js_content_bottom_toolbar',
    '.rich_media_tool_area_new',
    '#js_like_old_area',
    '#js_like_area',
    '.like_area',
    '#js_wx_tap_reader',
    '.wx_tap_reader',
    '#js_media_banner',
    '.media_banner',
    '#js_sponsor_tips',
    '.sponsor_tips',
    '#js_pay_bottom',
    '.pay_bottom_area',
    '#js_pay_area',
    '.pay_area',
    '#js_inclue_area',
    '.inclue_area',
    '#js_operate_area',
    '.operate_area',
    '#js_author_card',
    '.author_card',
    '#js_profile_qrcode',
    '.profile_qrcode',
    '#js_recom_article_area',
    '.recom_article_area',
    '#js_recom_article_list',
    '.recom_article_list',
    '#js_bottom_business_area',
    '.bottom_business_area',
    '#js_report_area',
    '.report_area',
    '#js_pc_qr_code_show',
    '.pc_qr_code_show',
    '#js_subscribe_area',
    '.subscribe_area',
    '#js_subscribe_btn',
    '.subscribe_btn',
    '#js_article_follow_btn',
    '.article_follow_btn',
    '#js_readmore3',
    '.read_more_btn',
    '#js_reader_qrcode',
    '.reader_qrcode',
    '#js_font_area',
    '.font_area',
    '#js_content_bottom',
    '.content_bottom_area',
    '#js_album_area',
    '.album_area',
    '#js_album_list',
    '.album_list',
    '#js_source_area',
    '.source_area',
    '#js_content_header',
    '.content_header_area',
    '#js_mini_program_bottom',
    '.mini_program_bottom',
    '#js_redpacketcover',
    '.redpacketcover',
    '#js_appmsg_copyright',
    '.appmsg_copyright_area',
    '#js_view_source',
    '.view_source',
    '.qr_code_pc',
    '#js_share_friend',
    '#js_share_moments',
    '#js_share_favorite',
    '#js_share_weibo',
    '#js_share_copy',
    '.share_btn',
    '.js_share_btn',
    '#js_share_btn_area',
    '.share_btn_area',
    '#js_more_read_area',
    '.more_read_area',
    '#js_tags_recommend',
    '.tags_recommend',
    '#js_comment_tip',
    '.comment_tip',
    '#js_write_comment',
    '.write_comment',
    '#js_selected_comment',
    '.selected_comment',
    '#js_comment_list',
    '.comment_list',
    '#js_cmt_list',
    '.cmt_list',
    '#js_cmt_header',
    '.cmt_header',
    '#js_cmt_switch',
    '.cmt_switch',
    '#js_cmt_search',
    '.cmt_search',
    '#js_cmt_more',
    '.cmt_more',
    '#js_cmt_no_comment',
    '.cmt_no_comment',
    '#js_cmt_loading',
    '.cmt_loading',
    '#js_cmt_error',
    '.cmt_error',
    '#js_cmt_single',
    '.cmt_single',
    '#js_cmt_reply',
    '.cmt_reply',
    '#js_cmt_like',
    '.cmt_like',
    '#js_cmt_report',
    '.cmt_report',
    '#js_cmt_delete',
    '.cmt_delete',
    '#js_cmt_avatar',
    '.cmt_avatar',
    '#js_cmt_nickname',
    '.cmt_nickname',
    '#js_cmt_text',
    '.cmt_text',
    '#js_cmt_time',
    '.cmt_time',
    '#js_cmt_location',
    '.cmt_location',
    '#js_cmt_img',
    '.cmt_img',
    '#js_cmt_video',
    '.cmt_video',
    '#js_cmt_audio',
    '.cmt_audio',
    '#js_cmt_link',
    '.cmt_link',
    '#js_cmt_forward',
    '.cmt_forward',
    '#js_cmt_share',
    '.cmt_share',
    '#js_cmt_collect',
    '.cmt_collect',
    '#js_cmt_tip_off',
    '.cmt_tip_off',
    '#js_cmt_author',
    '.cmt_author',
    '#js_cmt_sticky',
    '.cmt_sticky',
    '#js_cmt_hot',
    '.cmt_hot',
    '#js_cmt_new',
    '.cmt_new',
    '#js_cmt_image',
    '.cmt_image',
    '#js_cmt_emoji',
    '.cmt_emoji',
    '#js_cmt_at',
    '.cmt_at',
    '#js_cmt_topic',
    '.cmt_topic',
    '#js_cmt_tag',
    '.cmt_tag',
    '#js_cmt_fold',
    '.cmt_fold',
    '#js_cmt_expand',
    '.cmt_expand',
    '#js_cmt_reply_list',
    '.cmt_reply_list',
    '#js_cmt_reply_item',
    '.cmt_reply_item',
    '#js_cmt_reply_avatar',
    '.cmt_reply_avatar',
    '#js_cmt_reply_nickname',
    '.cmt_reply_nickname',
    '#js_cmt_reply_text',
    '.cmt_reply_text',
    '#js_cmt_reply_time',
    '.cmt_reply_time',
    '#js_cmt_reply_like',
    '.cmt_reply_like',
    '#js_cmt_reply_report',
    '.cmt_reply_report',
    '#js_cmt_reply_delete',
    '.cmt_reply_delete',
    '#js_cmt_reply_img',
    '.cmt_reply_img',
    '#js_cmt_reply_video',
    '.cmt_reply_video',
    '#js_cmt_reply_audio',
    '.cmt_reply_audio',
    '#js_cmt_reply_link',
    '.cmt_reply_link',
    '#js_cmt_reply_forward',
    '.cmt_reply_forward',
    '#js_cmt_reply_share',
    '.cmt_reply_share',
    '#js_cmt_reply_collect',
    '.cmt_reply_collect',
    '#js_cmt_reply_tip_off',
    '.cmt_reply_tip_off',
    '#js_cmt_reply_author',
    '.cmt_reply_author',
    '#js_cmt_reply_sticky',
    '.cmt_reply_sticky',
    '#js_cmt_reply_hot',
    '.cmt_reply_hot',
    '#js_cmt_reply_new',
    '.cmt_reply_new',
    '#js_cmt_reply_image',
    '.cmt_reply_image',
    '#js_cmt_reply_emoji',
    '.cmt_reply_emoji',
    '#js_cmt_reply_at',
    '.cmt_reply_at',
    '#js_cmt_reply_topic',
    '.cmt_reply_topic',
    '#js_cmt_reply_tag',
    '.cmt_reply_tag',
    '#js_cmt_reply_fold',
    '.cmt_reply_fold',
    '#js_cmt_reply_expand',
    '.cmt_reply_expand',
]


class WeixinParser(ArticleParser):
    platform = "weixin"
    platform_domains = ["weixin.qq.com", "mp.weixin.qq.com"]

    selectors = {
        'title': '#activity-name, .rich_media_title',
        'content': '#js_content, .rich_media_content',
        'author': '#js_name, .rich_media_meta_nickname',
        'date': '#publish_time, .rich_media_meta_date',
        'account': '#js_profile_qrcode .profile_nickname',
    }

    def __init__(self, config: ParserConfig = None):
        super().__init__(config)
        self.config.scroll_enabled = True

    async def extract_content(self, page: Page) -> Dict:
        result = {}

        try:
            title = await page.evaluate('''() => {
                const el = document.querySelector('#activity-name') ||
                           document.querySelector('.rich_media_title');
                return el ? el.textContent.trim() : '';
            }''')
            result['title'] = title or ''
        except Exception:
            result['title'] = ''

        try:
            remove_js = 'const removeSelectors = %s;' % str(_WEIXIN_REMOVE_SELECTORS)
            content_html = await page.evaluate('''%s
            () => {
                const contentEl = document.querySelector('#js_content') ||
                                  document.querySelector('.rich_media_content') ||
                                  document.querySelector('.rich_media_area_primary') ||
                                  document.querySelector('#img-content');
                if (!contentEl) return '';

                const clone = contentEl.cloneNode(true);

                for (const sel of removeSelectors) {
                    const els = clone.querySelectorAll(sel);
                    els.forEach(el => el.remove());
                }

                clone.querySelectorAll('script, style, svg, iframe, noscript').forEach(el => el.remove());

                return clone.innerHTML;
            }''' % remove_js)
            result['raw_html'] = content_html or ''
        except Exception:
            result['raw_html'] = ''

        try:
            remove_js = 'const removeSelectors = %s;' % str(_WEIXIN_REMOVE_SELECTORS)
            content = await page.evaluate('''%s
            () => {
                const contentEl = document.querySelector('#js_content') ||
                                  document.querySelector('.rich_media_content') ||
                                  document.querySelector('.rich_media_area_primary') ||
                                  document.querySelector('#img-content');
                if (!contentEl) return document.body.innerText;

                const clone = contentEl.cloneNode(true);

                for (const sel of removeSelectors) {
                    const els = clone.querySelectorAll(sel);
                    els.forEach(el => el.remove());
                }

                clone.querySelectorAll('script, style, svg, iframe, noscript').forEach(el => el.remove());

                const images = clone.querySelectorAll('img');
                images.forEach(img => {
                    const src = img.getAttribute('data-src') || img.getAttribute('src') || '';
                    const alt = img.getAttribute('alt') || '';
                    if (src && !src.startsWith('data:')) {
                        const span = document.createElement('span');
                        span.setAttribute('data-img-src', src);
                        span.textContent = `[图片: ${alt || src.split('/').pop().split('?')[0].split('#')[0]}]`;
                        img.replaceWith(span);
                    } else {
                        img.remove();
                    }
                });

                return clone.innerText;
            }''' % remove_js)
            result['content'] = content or ''
            result['raw_text'] = content or ''
        except Exception:
            result['content'] = ''
            result['raw_text'] = ''

        try:
            author = await page.evaluate('''() => {
                const el = document.querySelector('#js_name') ||
                           document.querySelector('.rich_media_meta_nickname');
                return el ? el.textContent.trim() : '';
            }''')
            result['author'] = author or ''
        except Exception:
            result['author'] = ''

        try:
            date = await page.evaluate('''() => {
                const el = document.querySelector('#publish_time') ||
                           document.querySelector('.rich_media_meta_date');
                return el ? (el.getAttribute('content') || el.textContent.trim()) : '';
            }''')
            result['publish_date'] = date or ''
        except Exception:
            result['publish_date'] = ''

        try:
            account = await page.evaluate('''() => {
                const el = document.querySelector('#js_profile_qrcode .profile_nickname');
                return el ? el.textContent.trim() : '';
            }''')
            result['account_name'] = account or ''
        except Exception:
            result['account_name'] = ''

        result['metadata'] = {
            'platform': 'weixin',
            'account': result.get('account_name', ''),
        }

        return result

    def post_process(self, content: Dict):
        raw_text = content.get('raw_text', '')
        if raw_text:
            content['raw_text'] = ContentCleanMixin.clean_weixin_text(raw_text)

        result = super().post_process(content)

        text = content.get('content', '') or content.get('raw_text', '')
        result.metadata['is_deleted'] = any(indicator in text for indicator in [
            '该内容已被发布者删除',
            '该公众号已被封禁',
            '此内容因违规无法查看'
        ])

        return result
