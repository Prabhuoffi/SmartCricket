import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../data/api_client.dart';
import '../ui/app_theme.dart';
import '../ui/brand.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({
    super.key,
    required this.onLogin,
    required this.onBack,
    this.notice,
  });

  /// The parent owns the configured ApiClient.
  final Future<void> Function(String email, String password) onLogin;
  final VoidCallback onBack;
  final String? notice;

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _form = GlobalKey<FormState>();
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _hidden = true;
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_busy || !_form.currentState!.validate()) return;
    FocusScope.of(context).unfocus();
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.onLogin(_email.text.trim(), _password.text);
      TextInput.finishAutofillContext();
    } on ApiException catch (error) {
      if (mounted) {
        setState(() => _error = error.message);
      }
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'We couldn\'t sign you in. Please try again.');
      }
    } finally {
      if (mounted) {
        setState(() => _busy = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: !_busy,
      child: Scaffold(
        appBar: AppBar(
          leading: IconButton(
            key: const Key('login-back'),
            tooltip: 'Back to home',
            onPressed: _busy ? null : widget.onBack,
            icon: const Icon(Icons.arrow_back_rounded),
          ),
          title: const Text(
            'Player login',
            style: TextStyle(fontSize: 17, fontWeight: FontWeight.w700),
          ),
        ),
        body: SafeArea(
          top: false,
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 520),
              child: SingleChildScrollView(
                keyboardDismissBehavior:
                    ScrollViewKeyboardDismissBehavior.onDrag,
                padding: const EdgeInsets.fromLTRB(24, 18, 24, 32),
                child: AutofillGroup(
                  child: Form(
                    key: _form,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const CricketBrand(),
                        const SizedBox(height: 34),
                        Text('WELCOME BACK', style: CricketFonts.heading(38)),
                        const SizedBox(height: 12),
                        Container(
                          width: 70,
                          height: 5,
                          decoration: BoxDecoration(
                            color: CricketColors.red,
                            borderRadius: BorderRadius.circular(5),
                          ),
                        ),
                        const SizedBox(height: 12),
                        const Text(
                          'Sign in to continue to your analyses.',
                          style: TextStyle(
                            color: CricketColors.muted,
                            height: 1.5,
                            fontSize: 15,
                          ),
                        ),

                        // ── Notice banner ──────────────────────────────────
                        if (widget.notice != null) ...[
                          const SizedBox(height: 18),
                          _Notice(text: widget.notice!, error: false),
                        ],
                        const SizedBox(height: 22),

                        // ── Email ──────────────────────────────────────────
                        TextFormField(
                          key: const Key('login-email'),
                          controller: _email,
                          enabled: !_busy,
                          keyboardType: TextInputType.emailAddress,
                          textInputAction: TextInputAction.next,
                          autofillHints: const [
                            AutofillHints.username,
                            AutofillHints.email,
                          ],
                          autocorrect: false,
                          decoration: const InputDecoration(
                            labelText: 'Email address',
                            prefixIcon: Icon(Icons.alternate_email_rounded),
                          ),
                          validator: (value) {
                            final email = (value ?? '').trim();
                            if (email.isEmpty) {
                              return 'Enter your email address';
                            }
                            if (!RegExp(
                              r'^[^\s@]+@[^\s@]+\.[^\s@]+$',
                            ).hasMatch(email)) {
                              return 'Enter a valid email address';
                            }
                            return null;
                          },
                        ),
                        const SizedBox(height: 18),

                        // ── Password ───────────────────────────────────────
                        TextFormField(
                          key: const Key('login-password'),
                          controller: _password,
                          enabled: !_busy,
                          obscureText: _hidden,
                          textInputAction: TextInputAction.done,
                          autofillHints: const [AutofillHints.password],
                          autocorrect: false,
                          enableSuggestions: false,
                          decoration: InputDecoration(
                            labelText: 'Password',
                            prefixIcon: const Icon(Icons.lock_outline_rounded),
                            suffixIcon: IconButton(
                              tooltip: _hidden
                                  ? 'Show password'
                                  : 'Hide password',
                              onPressed: _busy
                                  ? null
                                  : () => setState(() => _hidden = !_hidden),
                              icon: Icon(
                                _hidden
                                    ? Icons.visibility_outlined
                                    : Icons.visibility_off_outlined,
                              ),
                            ),
                          ),
                          validator: (value) => value == null || value.isEmpty
                              ? 'Enter your password'
                              : null,
                          onFieldSubmitted: (_) => _submit(),
                        ),

                        // ── Error banner ───────────────────────────────────
                        if (_error != null) ...[
                          const SizedBox(height: 18),
                          _Notice(text: _error!, error: true),
                        ],
                        const SizedBox(height: 24),

                        // ── Sign in button ─────────────────────────────────
                        SizedBox(
                          width: double.infinity,
                          child: FilledButton.icon(
                            key: const Key('login-submit'),
                            onPressed: _busy ? null : _submit,
                            iconAlignment: IconAlignment.end,
                            icon: _busy
                                ? const SizedBox.square(
                                    dimension: 18,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2,
                                    ),
                                  )
                                : const Icon(Icons.arrow_forward_rounded),
                            label: Text(
                              _busy ? 'Signing in…' : 'Sign in & practise',
                            ),
                          ),
                        ),
                        const SizedBox(height: 24),
                        const Text(
                          'Use your existing SmartCricket player account. Administrators sign in on the website.',
                          textAlign: TextAlign.center,
                          style: TextStyle(
                            color: CricketColors.muted,
                            fontSize: 13,
                            height: 1.5,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _Notice extends StatelessWidget {
  const _Notice({required this.text, required this.error});
  final String text;
  final bool error;

  @override
  Widget build(BuildContext context) => Semantics(
    liveRegion: true,
    child: Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: error ? const Color(0xFFFFE8E9) : const Color(0xFFE6F0E8),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            error ? Icons.error_outline_rounded : Icons.info_outline_rounded,
            color: error ? const Color(0xFF9D1730) : CricketColors.green,
            size: 20,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              text,
              style: TextStyle(
                color: error ? const Color(0xFF9D1730) : CricketColors.green,
                height: 1.45,
              ),
            ),
          ),
        ],
      ),
    ),
  );
}
