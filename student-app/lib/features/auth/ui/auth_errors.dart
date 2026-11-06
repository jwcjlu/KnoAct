import '../../../core/api_client.dart';
import '../data/auth_repository.dart';

/// 把认证/绑定/资料接口的异常翻译成孩子看得懂的提示
String authErrorText(Object e, {String fallback = '操作失败，请检查网络或后端服务'}) {
  if (e is NotAChildException) return '这个账号不是孩子账号，请使用孩子的登录名';
  if (e is ApiException) {
    switch (e.code) {
      case 'invalid_credentials':
        return '登录名或密码不正确';
      case 'please_register':
        return '还没有这个登录名，请先点「去注册」创建账号';
      case 'weak_password':
        return '密码至少 8 位，且需同时包含字母和数字';
      case 'invalid_login_name':
        return '登录名需 3–32 位，只能使用字母、数字或下划线';
      case 'login_name_taken':
        return '这个登录名已被使用，换一个试试';
      case 'invalid_code':
        return '验证码或邀请码不正确';
      case 'phone_not_verified':
        return '该账号未绑定手机号，无法使用验证码登录';
      case 'archived':
        return '该账号已停用';
      case 'code_used':
        return '邀请码已被使用';
      case 'code_expired':
        return '邀请码已过期，请让家长重新生成';
      case 'already_bound':
        return '你已经绑定了家长';
      case 'parent_not_found':
        return '没有找到这个家长账号';
      case 'invalid_display_name':
        return '昵称不能为空，且不超过 64 个字';
      case 'invalid_birth_month':
        return '出生年月格式应为 YYYY-MM';
      case 'invalid_gender':
        return '性别选项无效';
    }
    if (e.code != null && e.statusCode != null && e.statusCode! < 500 && e.statusCode != 401) {
      // 未知的 4xx 业务错误码（如密码强度、登录名格式）直接展示，方便排查
      return '操作失败：${e.code}';
    }
  }
  return fallback;
}
