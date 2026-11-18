import 'dart:async';
import 'dart:io';
import 'firebase_options.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:qr_flutter/qr_flutter.dart';
import 'package:share_plus/share_plus.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:file_picker/file_picker.dart';
import 'services/auth_service.dart';
import 'services/event_api_service.dart';
import 'services/photo_upload_service.dart';
import 'services/on_device_gallery_service.dart';

const _primary = Color(0xFF4338CA);
const _secondary = Color(0xFFE0E7FF);
const _accent = Color(0xFF0F766E);
const _highlight = Color(0xFFF59E0B);
const _background = Color(0xFFF7F7FB);

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  var firebaseReady = false;
  try {
    await Firebase.initializeApp(
      options: DefaultFirebaseOptions.currentPlatform,
    );
    firebaseReady = true;
  } on FirebaseException {
    // The app remains runnable so configuration errors can be shown in-app.
  }
  runApp(SnapSortApp(firebaseReady: firebaseReady));
}

class SnapSortApp extends StatelessWidget {
  const SnapSortApp({super.key, this.firebaseReady = false});

  final bool firebaseReady;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SnapSort',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        scaffoldBackgroundColor: _background,
        colorScheme: ColorScheme.fromSeed(
          seedColor: _primary,
          primary: _primary,
          secondary: _accent,
          surface: Colors.white,
        ),
        inputDecorationTheme: InputDecorationTheme(
          filled: true,
          fillColor: Colors.white,
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(16),
            borderSide: BorderSide.none,
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(16),
            borderSide: BorderSide(color: Colors.black.withValues(alpha: .08)),
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(16),
            borderSide: const BorderSide(color: _primary, width: 2),
          ),
        ),
        elevatedButtonTheme: ElevatedButtonThemeData(
          style: ElevatedButton.styleFrom(
            backgroundColor: _primary,
            foregroundColor: Colors.white,
            minimumSize: const Size.fromHeight(54),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(16),
            ),
          ),
        ),
        textTheme: const TextTheme(
          headlineLarge: TextStyle(
            fontWeight: FontWeight.w800,
            letterSpacing: -1,
          ),
          headlineSmall: TextStyle(fontWeight: FontWeight.w800),
          titleLarge: TextStyle(fontWeight: FontWeight.w700),
          titleMedium: TextStyle(fontWeight: FontWeight.w700),
        ),
      ),
      home: SplashScreen(firebaseReady: firebaseReady),
    );
  }
}

class LogoMark extends StatelessWidget {
  const LogoMark({super.key, this.large = false});

  final bool large;

  @override
  Widget build(BuildContext context) {
    final size = large ? 76.0 : 44.0;
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(large ? 24 : 14),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(large ? 24 : 14),
        child: Image.asset(
          'assets/snapsort_logo.png',
          fit: BoxFit.cover,
          errorBuilder: (_, error, stackTrace) => Icon(
            Icons.center_focus_strong_rounded,
            color: _primary,
            size: large ? 42 : 25,
          ),
        ),
      ),
    );
  }
}

class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key, required this.firebaseReady});

  final bool firebaseReady;

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> {
  @override
  void initState() {
    super.initState();
    Timer(const Duration(milliseconds: 900), () {
      if (mounted) {
        Navigator.of(context).pushReplacement(
          MaterialPageRoute(
            builder: (_) => widget.firebaseReady
                ? const AuthGate()
                : const OnboardingScreen(),
          ),
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            LogoMark(large: true),
            SizedBox(height: 22),
            Text(
              'SnapSort',
              style: TextStyle(fontSize: 34, fontWeight: FontWeight.w800),
            ),
            SizedBox(height: 8),
            Text('Find your photos, without the scrolling.'),
          ],
        ),
      ),
    );
  }
}

class AuthGate extends StatelessWidget {
  const AuthGate({super.key});

  @override
  Widget build(BuildContext context) {
    return StreamBuilder(
      stream: AuthService.instance.authStateChanges,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Scaffold(
            body: Center(child: CircularProgressIndicator()),
          );
        }
        return snapshot.data == null
            ? const OnboardingScreen()
            : const RoleSelectionScreen();
      },
    );
  }
}

class OnboardingScreen extends StatefulWidget {
  const OnboardingScreen({super.key});

  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  final _pages = const [
    (
      'Every moment, easy to find.',
      'SnapSort brings your event memories together in one beautiful place.',
      Icons.photo_library_outlined,
    ),
    (
      'Your photos, personalized.',
      'A simple, secure way for attendees to discover the moments they are in.',
      Icons.auto_awesome_outlined,
    ),
    (
      'Built for every event.',
      'Organize, share, and enjoy the gallery without the endless scrolling.',
      Icons.celebration_outlined,
    ),
  ];
  int _index = 0;

  @override
  Widget build(BuildContext context) {
    final page = _pages[_index];
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  const LogoMark(),
                  const Spacer(),
                  TextButton(
                    onPressed: () => _openAuth(context),
                    child: const Text('Skip'),
                  ),
                ],
              ),
              Expanded(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Container(
                      width: 170,
                      height: 170,
                      decoration: BoxDecoration(
                        color: _secondary,
                        borderRadius: BorderRadius.circular(52),
                      ),
                      child: Icon(page.$3, size: 78, color: _primary),
                    ),
                    const SizedBox(height: 42),
                    Text(
                      page.$1,
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.headlineSmall,
                    ),
                    const SizedBox(height: 14),
                    Text(
                      page.$2,
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                        color: Colors.black54,
                        height: 1.5,
                      ),
                    ),
                  ],
                ),
              ),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: List.generate(
                  _pages.length,
                  (i) => _Dot(active: i == _index),
                ),
              ),
              const SizedBox(height: 24),
              ElevatedButton(
                onPressed: () {
                  if (_index == _pages.length - 1) {
                    _openAuth(context);
                  } else {
                    setState(() => _index++);
                  }
                },
                child: Text(
                  _index == _pages.length - 1 ? 'Get started' : 'Continue',
                ),
              ),
              const SizedBox(height: 12),
              OutlinedButton(
                onPressed: () => _openAuth(context),
                style: OutlinedButton.styleFrom(
                  minimumSize: const Size.fromHeight(54),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                  ),
                ),
                child: const Text('I already have an account'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _openAuth(BuildContext context) {
    Navigator.of(
      context,
    ).pushReplacement(MaterialPageRoute(builder: (_) => const LoginScreen()));
  }
}

class _Dot extends StatelessWidget {
  const _Dot({required this.active});
  final bool active;

  @override
  Widget build(BuildContext context) => AnimatedContainer(
    duration: const Duration(milliseconds: 200),
    margin: const EdgeInsets.symmetric(horizontal: 4),
    width: active ? 24 : 8,
    height: 8,
    decoration: BoxDecoration(
      color: active ? _primary : _secondary,
      borderRadius: BorderRadius.circular(8),
    ),
  );
}

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _email = TextEditingController();
  final _password = TextEditingController();
  String? _error;
  bool _busy = false;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AuthScaffold(
      title: 'Welcome back',
      subtitle: 'Sign in to find your moments.',
      child: Form(
        key: _formKey,
        child: Column(
          children: [
            TextFormField(
              controller: _email,
              keyboardType: TextInputType.emailAddress,
              decoration: const InputDecoration(
                labelText: 'Email address',
                prefixIcon: Icon(Icons.email_outlined),
              ),
              validator: (v) => v == null || !v.contains('@')
                  ? 'Enter a valid email address'
                  : null,
            ),
            const SizedBox(height: 14),
            TextFormField(
              controller: _password,
              obscureText: true,
              decoration: const InputDecoration(
                labelText: 'Password',
                prefixIcon: Icon(Icons.lock_outline),
              ),
              validator: (v) => v == null || v.length < 6
                  ? 'Use at least 6 characters'
                  : null,
            ),
            Align(
              alignment: Alignment.centerRight,
              child: TextButton(
                onPressed: () => Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (_) => const ForgotPasswordScreen(),
                  ),
                ),
                child: const Text('Forgot password?'),
              ),
            ),
            const SizedBox(height: 12),
            if (_error != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Text(
                  _error!,
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: Colors.red),
                ),
              ),
            ElevatedButton(
              onPressed: _busy ? null : _signIn,
              child: _busy
                  ? const SizedBox(
                      height: 22,
                      width: 22,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Text('Sign in'),
            ),
            const SizedBox(height: 18),
            TextButton(
              onPressed: () => Navigator.of(
                context,
              ).push(MaterialPageRoute(builder: (_) => const SignUpScreen())),
              child: const Text('New to SnapSort? Create an account'),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _signIn() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await AuthService.instance.signIn(
        email: _email.text,
        password: _password.text,
      );
      if (mounted) {
        Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => const RoleSelectionScreen()),
        );
      }
    } catch (error) {
      if (mounted) setState(() => _error = authErrorMessage(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }
}

class AuthScaffold extends StatelessWidget {
  const AuthScaffold({
    super.key,
    required this.title,
    required this.subtitle,
    required this.child,
  });
  final String title;
  final String subtitle;
  final Widget child;

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      backgroundColor: Colors.transparent,
      leading: const BackButton(),
    ),
    body: SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(24, 16, 24, 32),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const LogoMark(),
            const SizedBox(height: 28),
            Text(title, style: Theme.of(context).textTheme.headlineLarge),
            const SizedBox(height: 8),
            Text(
              subtitle,
              style: Theme.of(
                context,
              ).textTheme.bodyLarge?.copyWith(color: Colors.black54),
            ),
            const SizedBox(height: 32),
            child,
          ],
        ),
      ),
    ),
  );
}

class SignUpScreen extends StatefulWidget {
  const SignUpScreen({super.key});
  @override
  State<SignUpScreen> createState() => _SignUpScreenState();
}

class _SignUpScreenState extends State<SignUpScreen> {
  final _formKey = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _email = TextEditingController();
  final _password = TextEditingController();
  String? _error;
  bool _busy = false;

  @override
  void dispose() {
    _name.dispose();
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AuthScaffold(
    title: 'Create your account',
    subtitle: 'Start finding your photos in a few steps.',
    child: Form(
      key: _formKey,
      child: Column(
        children: [
          TextFormField(
            controller: _name,
            decoration: const InputDecoration(
              labelText: 'Full name',
              prefixIcon: Icon(Icons.person_outline),
            ),
            validator: (v) =>
                v == null || v.trim().length < 2 ? 'Enter your name' : null,
          ),
          const SizedBox(height: 14),
          TextFormField(
            controller: _email,
            keyboardType: TextInputType.emailAddress,
            decoration: const InputDecoration(
              labelText: 'Email address',
              prefixIcon: Icon(Icons.email_outlined),
            ),
            validator: (v) => v == null || !v.contains('@')
                ? 'Enter a valid email address'
                : null,
          ),
          const SizedBox(height: 14),
          TextFormField(
            controller: _password,
            obscureText: true,
            decoration: const InputDecoration(
              labelText: 'Password',
              prefixIcon: Icon(Icons.lock_outline),
            ),
            validator: (v) =>
                v == null || v.length < 6 ? 'Use at least 6 characters' : null,
          ),
          const SizedBox(height: 24),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Text(
                _error!,
                textAlign: TextAlign.center,
                style: const TextStyle(color: Colors.red),
              ),
            ),
          ElevatedButton(
            onPressed: _busy ? null : _signUp,
            child: _busy
                ? const SizedBox(
                    height: 22,
                    width: 22,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Text('Continue'),
          ),
        ],
      ),
    ),
  );

  Future<void> _signUp() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await AuthService.instance.createAccount(
        name: _name.text,
        email: _email.text,
        password: _password.text,
      );
      if (mounted) {
        Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => const RoleSelectionScreen()),
        );
      }
    } catch (error) {
      if (mounted) {
        setState(
          () => _error = error is EventApiException
              ? error.message
              : authErrorMessage(error),
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }
}

class ForgotPasswordScreen extends StatefulWidget {
  const ForgotPasswordScreen({super.key});
  @override
  State<ForgotPasswordScreen> createState() => _ForgotPasswordScreenState();
}

class _ForgotPasswordScreenState extends State<ForgotPasswordScreen> {
  final _email = TextEditingController();
  String? _message;
  bool _busy = false;
  @override
  void dispose() {
    _email.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AuthScaffold(
    title: 'Reset your password',
    subtitle: 'We will send a secure reset link to your email.',
    child: Column(
      children: [
        TextField(
          controller: _email,
          keyboardType: TextInputType.emailAddress,
          decoration: const InputDecoration(
            labelText: 'Email address',
            prefixIcon: Icon(Icons.email_outlined),
          ),
        ),
        const SizedBox(height: 24),
        ElevatedButton(
          onPressed: _busy ? null : _resetPassword,
          child: _busy
              ? const SizedBox(
                  height: 22,
                  width: 22,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Text('Send reset link'),
        ),
        if (_message != null)
          Padding(
            padding: const EdgeInsets.only(top: 18),
            child: Text(
              _message!,
              textAlign: TextAlign.center,
              style: TextStyle(
                color: _message!.startsWith('If') ? _accent : Colors.red,
              ),
            ),
          ),
      ],
    ),
  );

  Future<void> _resetPassword() async {
    if (!_email.text.contains('@')) {
      setState(() => _message = 'Enter a valid email address.');
      return;
    }
    setState(() {
      _busy = true;
      _message = null;
    });
    try {
      await AuthService.instance.sendPasswordReset(_email.text);
      if (mounted) {
        setState(
          () => _message = 'If an account exists, a reset link is on its way.',
        );
      }
    } catch (error) {
      if (mounted) setState(() => _message = authErrorMessage(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }
}

class RoleSelectionScreen extends StatefulWidget {
  const RoleSelectionScreen({super.key});
  @override
  State<RoleSelectionScreen> createState() => _RoleSelectionScreenState();
}

class _RoleSelectionScreenState extends State<RoleSelectionScreen> {
  UserRole _role = UserRole.attendee;
  bool _busy = false;
  String? _error;

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Set up your profile')),
    body: ListView(
      padding: const EdgeInsets.all(24),
      children: [
        Text(
          'How will you use SnapSort?',
          style: Theme.of(context).textTheme.headlineSmall,
        ),
        const SizedBox(height: 8),
        const Text(
          'Choose the experience that fits you best. You can update this later.',
        ),
        const SizedBox(height: 24),
        ...UserRole.values.map(
          (role) => _RoleCard(
            role: role,
            selected: _role == role,
            onTap: () => setState(() => _role = role),
          ),
        ),
        const SizedBox(height: 18),
        if (_error != null)
          Text(
            _error!,
            textAlign: TextAlign.center,
            style: const TextStyle(color: Colors.red),
          ),
        ElevatedButton(
          onPressed: _busy ? null : _continue,
          child: _busy
              ? const SizedBox(
                  height: 22,
                  width: 22,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Text('Continue to SnapSort'),
        ),
      ],
    ),
  );

  Future<void> _continue() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await AuthService.instance.saveRole(_role);
      await EventApiService().updateRole(_role.name);
      if (mounted) {
        Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => DashboardScreen(role: _role)),
        );
      }
    } catch (error) {
      if (mounted) setState(() => _error = authErrorMessage(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }
}

class _RoleCard extends StatelessWidget {
  const _RoleCard({
    required this.role,
    required this.selected,
    required this.onTap,
  });
  final UserRole role;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final data = {
      UserRole.organizer: (
        'Organizer',
        'Create events and manage your galleries',
        Icons.event_note_outlined,
      ),
      UserRole.photographer: (
        'Photographer',
        'Upload and organize event photos',
        Icons.camera_alt_outlined,
      ),
      UserRole.attendee: (
        'Attendee',
        'Find the photos you are in',
        Icons.person_search_outlined,
      ),
    }[role]!;
    return Card(
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(18),
        side: BorderSide(
          color: selected ? _primary : Colors.transparent,
          width: 2,
        ),
      ),
      child: ListTile(
        onTap: onTap,
        contentPadding: const EdgeInsets.all(12),
        leading: CircleAvatar(
          backgroundColor: selected ? _secondary : _background,
          foregroundColor: _primary,
          child: Icon(data.$3),
        ),
        title: Text(
          data.$1,
          style: const TextStyle(fontWeight: FontWeight.w700),
        ),
        subtitle: Text(data.$2),
        trailing: Icon(
          selected ? Icons.radio_button_checked : Icons.radio_button_off,
          color: selected ? _primary : Colors.black26,
        ),
      ),
    );
  }
}

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key, required this.role});
  final UserRole role;

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  int _selectedIndex = 0;

  UserRole get role => widget.role;

  String get _title => switch (role) {
    UserRole.organizer => 'Organizer dashboard',
    UserRole.photographer => 'Photographer dashboard',
    UserRole.attendee => 'Your photo journey',
  };

  @override
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(_title),
      actions: [
        IconButton(
          onPressed: () => ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('No new notifications.')),
          ),
          icon: const Icon(Icons.notifications_none_rounded),
        ),
        IconButton(
          tooltip: 'Sign out',
          onPressed: () async {
            try {
              await AuthService.instance.signOut();
              if (context.mounted) {
                Navigator.of(context).pushAndRemoveUntil(
                  MaterialPageRoute(builder: (_) => const LoginScreen()),
                  (_) => false,
                );
              }
            } catch (error) {
              if (context.mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text(authErrorMessage(error))),
                );
              }
            }
          },
          icon: const Icon(Icons.logout_rounded),
        ),
        const SizedBox(width: 8),
      ],
    ),
    body: SafeArea(
      child: _selectedIndex == 0
          ? ListView(
        padding: const EdgeInsets.all(20),
        children: [
          _Greeting(role: role),
          const SizedBox(height: 22),
          _DashboardContent(role: role),
        ],
      )
          : _selectedIndex == 1
          ? PhotosScreen(role: role)
          : _ProfileScreen(role: role),
    ),
    bottomNavigationBar: NavigationBar(
      selectedIndex: _selectedIndex,
      onDestinationSelected: (index) => setState(() => _selectedIndex = index),
      destinations: const [
        NavigationDestination(
          icon: Icon(Icons.grid_view_rounded),
          label: 'Home',
        ),
        NavigationDestination(
          icon: Icon(Icons.photo_library_outlined),
          label: 'Photos',
        ),
        NavigationDestination(
          icon: Icon(Icons.person_outline),
          label: 'Profile',
        ),
      ],
    ),
  );
}

class _Greeting extends StatelessWidget {
  const _Greeting({required this.role});
  final UserRole role;
  @override
  Widget build(BuildContext context) => Row(
    children: [
      const CircleAvatar(
        radius: 26,
        backgroundColor: _secondary,
        child: Icon(Icons.person, color: _primary),
      ),
      const SizedBox(width: 14),
      Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Good to see you',
            style: Theme.of(
              context,
            ).textTheme.bodyMedium?.copyWith(color: Colors.black54),
          ),
          const Text(
            'Welcome to SnapSort',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
          ),
        ],
      ),
    ],
  );
}

class _ProfileScreen extends StatelessWidget {
  const _ProfileScreen({required this.role});

  final UserRole role;

  @override
  Widget build(BuildContext context) {
    final user = AuthService.instance.currentUser;
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Text('Profile', style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 18),
        Card(
          elevation: 0,
          child: ListTile(
            leading: const CircleAvatar(child: Icon(Icons.person)),
            title: Text(
              user?.displayName?.isNotEmpty == true
                  ? user!.displayName!
                  : 'SnapSort user',
            ),
            subtitle: Text('${user?.email ?? ''}\nRole: ${role.name}'),
          ),
        ),
        const SizedBox(height: 16),
        const ListTile(
          leading: Icon(Icons.notifications_none),
          title: Text('Notifications'),
          subtitle: Text('You are all caught up.'),
        ),
        const SizedBox(height: 16),
        FilledButton.icon(
          onPressed: () async {
            await AuthService.instance.signOut();
            if (context.mounted) {
              Navigator.of(context).pushAndRemoveUntil(
                MaterialPageRoute(builder: (_) => const LoginScreen()),
                (_) => false,
              );
            }
          },
          icon: const Icon(Icons.logout),
          label: const Text('Sign out'),
        ),
      ],
    );
  }
}

class PhotosScreen extends StatefulWidget {
  const PhotosScreen({super.key, required this.role});

  @override
  State<PhotosScreen> createState() => _PhotosScreenState();

  final UserRole role;
}

class _PhotoEntry {
  const _PhotoEntry({required this.id, this.url, this.localPath});

  final String id;
  final String? url;
  final String? localPath;
}

class _PhotoGroup {
  const _PhotoGroup({required this.eventName, required this.photos});

  final String eventName;
  final List<_PhotoEntry> photos;
}

class _PhotosScreenState extends State<PhotosScreen> {
  final _api = EventApiService();
  bool _loading = true;
  String? _error;
  List<_PhotoGroup> _groups = [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      if (widget.role == UserRole.attendee) {
        final saved = await OnDeviceGalleryService().savedEventPhotos();
        final grouped = <String, List<_PhotoEntry>>{};
        for (final photo in saved) {
          grouped
              .putIfAbsent(photo.eventName, () => [])
              .add(_PhotoEntry(id: photo.photoId, localPath: photo.path));
        }
        if (mounted) {
          setState(
            () => _groups = grouped.entries
                .map((entry) => _PhotoGroup(
                      eventName: entry.key,
                      photos: entry.value,
                    ))
                .toList(),
          );
        }
      } else {
        final photos = await _api.listUploadedPhotos();
        final grouped = <String, List<_PhotoEntry>>{};
        for (final photo in photos) {
          grouped
              .putIfAbsent(photo.eventName, () => [])
              .add(_PhotoEntry(id: photo.id, url: photo.photoUrl));
        }
        if (mounted) {
          setState(
            () => _groups = grouped.entries
                .map((entry) => _PhotoGroup(
                      eventName: entry.key,
                      photos: entry.value,
                    ))
                .toList(),
          );
        }
      }
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(
        widget.role == UserRole.attendee ? 'My event photos' : 'Event photos',
      ),
      actions: [IconButton(onPressed: _load, icon: const Icon(Icons.refresh))],
    ),
    body: _loading
        ? const Center(child: CircularProgressIndicator())
        : _error != null
        ? _ErrorState(message: _error!, onRetry: _load)
        : _groups.isEmpty
        ? const Center(child: Text('Your event photos will appear here.'))
        : ListView(
            padding: const EdgeInsets.all(16),
            children: _groups
                .map(
                  (group) => Card(
                    elevation: 0,
                    margin: const EdgeInsets.only(bottom: 16),
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Row(
                            children: [
                              Expanded(
                                child: Text(
                                  group.eventName,
                                  style: Theme.of(context)
                                      .textTheme
                                      .titleMedium,
                                ),
                              ),
                              if (widget.role == UserRole.attendee)
                                TextButton.icon(
                                  onPressed: () => _downloadAll(group),
                                  icon: const Icon(Icons.download),
                                  label: const Text('Download all'),
                                ),
                            ],
                          ),
                          const SizedBox(height: 10),
                          GridView.builder(
                            shrinkWrap: true,
                            physics: const NeverScrollableScrollPhysics(),
                            itemCount: group.photos.length,
                            gridDelegate:
                                const SliverGridDelegateWithFixedCrossAxisCount(
                                  crossAxisCount: 2,
                                  crossAxisSpacing: 8,
                                  mainAxisSpacing: 8,
                                ),
                            itemBuilder: (_, index) {
                              final photo = group.photos[index];
                              return ClipRRect(
                                borderRadius: BorderRadius.circular(8),
                                child: photo.localPath != null
                                    ? Image.file(
                                        File(photo.localPath!),
                                        fit: BoxFit.cover,
                                      )
                                    : Image.network(
                                        photo.url!,
                                        fit: BoxFit.cover,
                                      ),
                              );
                            },
                          ),
                        ],
                      ),
                    ),
                  ),
                )
                .toList(),
          ),
  );

  Future<void> _downloadAll(_PhotoGroup group) async {
    var saved = 0;
    for (final photo in group.photos) {
      try {
        if (photo.localPath != null) {
          saved++;
          continue;
        }
        final response = await http.get(Uri.parse(photo.url!));
        if (response.statusCode >= 200 && response.statusCode < 300) {
          await OnDeviceGalleryService().saveRemoteImage(
            response.bodyBytes,
            'snapsort_${photo.id}.jpg',
          );
          saved++;
        }
      } catch (_) {
        // Continue downloading the remaining photos.
      }
    }
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            '$saved of ${group.photos.length} photos saved to Pictures/SnapSort.',
          ),
        ),
      );
    }
  }
}

class _DashboardContent extends StatefulWidget {
  const _DashboardContent({required this.role});
  final UserRole role;

  @override
  State<_DashboardContent> createState() => _DashboardContentState();
}

class _DashboardContentState extends State<_DashboardContent> {
  final _api = EventApiService();
  List<EventRecord> _events = [];
  bool _loading = true;

  UserRole get role => widget.role;

  @override
  void initState() {
    super.initState();
    _loadEvents();
  }

  Future<void> _loadEvents() async {
    try {
      final events = role == UserRole.organizer
          ? await _api.listEvents()
          : role == UserRole.photographer
          ? await _api.listPhotographerEvents()
          : await _api.listAttendeeEvents();
      if (mounted) setState(() => _events = events);
    } catch (_) {
      if (mounted) setState(() => _events = []);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final isAttendee = role == UserRole.attendee;
    final isPhotographer = role == UserRole.photographer;
    final headline = isAttendee
        ? 'Find your event photos'
        : isPhotographer
        ? 'Your assignments'
        : 'Bring an event to life';
    final body = isAttendee
        ? 'Join an event to discover the moments you are in.'
        : isPhotographer
        ? 'Assigned events and upload tools will appear here.'
        : 'Create your first event and invite your photo team.';
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Container(
          padding: const EdgeInsets.all(22),
          decoration: BoxDecoration(
            color: _primary,
            borderRadius: BorderRadius.circular(24),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                headline,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 24,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                body,
                style: const TextStyle(color: Colors.white70, height: 1.4),
              ),
              const SizedBox(height: 20),
              FilledButton.icon(
                onPressed: () {
                  if (role == UserRole.organizer) {
                    Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) => const OrganizerEventsScreen(),
                      ),
                    );
                  } else if (role == UserRole.photographer) {
                    Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) => const PhotographerEventsScreen(),
                      ),
                    );
                  } else {
                    Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) => const AttendeeEventsScreen(),
                      ),
                    );
                  }
                },
                style: FilledButton.styleFrom(
                  backgroundColor: Colors.white,
                  foregroundColor: _primary,
                ),
                icon: Icon(isAttendee ? Icons.qr_code_scanner : Icons.add),
                label: Text(
                  isAttendee
                      ? 'Join an event'
                      : isPhotographer
                      ? 'View assignments'
                      : 'Create event',
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 24),
        Text(
          isAttendee ? 'Your events' : 'Overview',
          style: Theme.of(context).textTheme.titleLarge,
        ),
        const SizedBox(height: 12),
        if (_loading)
          const Center(child: CircularProgressIndicator())
        else if (_events.isEmpty)
          Card(
            elevation: 0,
            child: Padding(
              padding: const EdgeInsets.all(22),
              child: Text(
                isAttendee
                    ? 'Join an event with a code or QR scan to get started.'
                    : 'No events yet.',
                textAlign: TextAlign.center,
              ),
            ),
          )
        else
          ..._events.map(
            (event) => role == UserRole.organizer
                ? _OrganizerEventCard(event: event)
                : Card(
                    elevation: 0,
                    child: ListTile(
                      leading: const Icon(Icons.event, color: _primary),
                      title: Text(event.name),
                      subtitle: Text(event.description ?? event.eventCode),
                      trailing: Text(event.status),
                    ),
                  ),
          ),
        if (isAttendee) ...[
          const SizedBox(height: 16),
          OutlinedButton.icon(
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const DeviceGalleryScreen()),
            ),
            icon: const Icon(Icons.folder_copy_outlined),
            label: const Text('Organize device gallery'),
          ),
        ],
      ],
    );
  }
}

class _OrganizerEventCard extends StatefulWidget {
  const _OrganizerEventCard({required this.event});

  final EventRecord event;

  @override
  State<_OrganizerEventCard> createState() => _OrganizerEventCardState();
}

class _OrganizerEventCardState extends State<_OrganizerEventCard> {
  final _api = EventApiService();
  EventPlan? _plan;
  bool _loading = true;
  bool _working = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadPlan();
  }

  Future<void> _loadPlan() async {
    try {
      final plan = await _api.getEventPlan(widget.event.id);
      if (mounted) setState(() => _plan = plan);
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _upgrade() async {
    final tier = await showModalBottomSheet<String>(
      context: context,
      builder: (context) => SafeArea(
        child: Wrap(
          children: [
            const ListTile(
              title: Text('Upgrade event'),
              subtitle: Text('Choose a paid plan to unlock higher limits.'),
            ),
            ListTile(
              leading: const Icon(Icons.photo_library_outlined),
              title: const Text('Standard'),
              onTap: () => Navigator.pop(context, 'standard'),
            ),
            ListTile(
              leading: const Icon(Icons.auto_awesome_outlined),
              title: const Text('Pro'),
              onTap: () => Navigator.pop(context, 'pro'),
            ),
          ],
        ),
      ),
    );
    if (tier == null || !mounted) return;
    setState(() => _working = true);
    try {
      final checkout = await _api.createCheckout(
        eventId: widget.event.id,
        tier: tier,
      );
      final opened = await launchUrl(
        Uri.parse(checkout.checkoutUrl),
        mode: LaunchMode.externalApplication,
      );
      if (!opened) throw StateError('Could not open the payment page.');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Complete payment, then refresh this event plan.'),
          ),
        );
      }
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(error.toString())));
      }
    } finally {
      if (mounted) setState(() => _working = false);
    }
  }

  String _usage(EventPlan plan) {
    final limits = plan.limits;
    if (limits == null) return 'No active plan';
    return '${plan.photoCount}/${limits.maxPhotos} photos • '
        '${_formatBytes(plan.storageBytes)}/${_formatBytes(limits.maxStorageBytes)} • '
        '${plan.matchingSearches}/${limits.maxMatchingSearches} searches';
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 0,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: _loading
            ? const LinearProgressIndicator()
            : Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: const Icon(Icons.event, color: _primary),
                    title: Text(widget.event.name),
                    subtitle: Text(widget.event.description ?? widget.event.eventCode),
                    trailing: Text(widget.event.status),
                  ),
                  if (_error != null)
                    Text(_error!, style: TextStyle(color: Colors.red.shade700))
                  else ...[
                    Text(
                      'Plan: ${_plan?.tier ?? 'Not activated'} (${_plan?.status ?? 'expired'})',
                      style: const TextStyle(fontWeight: FontWeight.w700),
                    ),
                    const SizedBox(height: 6),
                    Text(_plan == null ? '' : _usage(_plan!)),
                    const SizedBox(height: 10),
                    Align(
                      alignment: Alignment.centerRight,
                      child: OutlinedButton.icon(
                        onPressed: _working ? null : _upgrade,
                        icon: const Icon(Icons.upgrade),
                        label: Text(_working ? 'Opening...' : 'Upgrade'),
                      ),
                    ),
                  ],
                ],
              ),
      ),
    );
  }
}

String _formatBytes(int bytes) {
  if (bytes < 1024 * 1024) return '${(bytes / 1024).ceil()} KB';
  if (bytes < 1024 * 1024 * 1024) {
    return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
  }
  return '${(bytes / (1024 * 1024 * 1024)).toStringAsFixed(1)} GB';
}

class DeviceGalleryScreen extends StatefulWidget {
  const DeviceGalleryScreen({super.key});

  @override
  State<DeviceGalleryScreen> createState() => _DeviceGalleryScreenState();
}

class _DeviceGalleryScreenState extends State<DeviceGalleryScreen> {
  final _service = OnDeviceGalleryService();
  final _excluded = <String>{};
  List<DevicePhoto> _photos = [];
  bool _loading = false;
  bool _organizing = false;
  bool _scanningEnabled = true;
  String? _error;

  Future<void> _scan() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final photos = await _service.scan();
      if (mounted) setState(() => _photos = photos);
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _organize() async {
    final selected = _photos
        .where((photo) => !_excluded.contains(photo.id))
        .toList();
    if (selected.isEmpty) {
      setState(() => _error = 'Select at least one photo to organize.');
      return;
    }
    setState(() {
      _organizing = true;
      _error = null;
    });
    try {
      await _service.organize(selected);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              '${selected.length} photos added to Pictures/SnapSort.',
            ),
          ),
        );
      }
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _organizing = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Device gallery'),
      actions: [
        Switch(
          value: _scanningEnabled,
          onChanged: _organizing
              ? null
              : (value) => setState(() => _scanningEnabled = value),
        ),
      ],
    ),
    body: ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Text(
          'Private on-device organization',
          style: Theme.of(context).textTheme.headlineSmall,
        ),
        const SizedBox(height: 8),
        const Text(
          'Photos stay on this device. SnapSort does not upload your personal gallery or use it for event matching.',
        ),
        const SizedBox(height: 16),
        OutlinedButton.icon(
          onPressed: !_scanningEnabled || _loading ? null : _scan,
          icon: const Icon(Icons.photo_library_outlined),
          label: Text(_loading ? 'Scanning...' : 'Scan device photos'),
        ),
        if (_error != null)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 12),
            child: Text(_error!, style: const TextStyle(color: Colors.red)),
          ),
        if (_photos.isNotEmpty) ...[
          Text(
            '${_photos.length} unique photos found',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 8),
          ..._photos.map(
            (photo) => CheckboxListTile(
              value: !_excluded.contains(photo.id),
              onChanged: _organizing
                  ? null
                  : (included) => setState(() {
                      if (included == true) {
                        _excluded.remove(photo.id);
                      } else {
                        _excluded.add(photo.id);
                      }
                    }),
              title: Text(
                photo.name,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              subtitle: const Text('On-device only'),
              secondary: const Icon(Icons.image_outlined, color: _primary),
            ),
          ),
          const SizedBox(height: 12),
          ElevatedButton(
            onPressed: _organizing ? null : _organize,
            child: Text(
              _organizing ? 'Organizing...' : 'Organize selected photos',
            ),
          ),
        ],
        const SizedBox(height: 18),
        const Text(
          'Person-based grouping is intentionally unavailable until a verified on-device face model is added. No simulated groups are shown.',
          style: TextStyle(color: Colors.black54),
        ),
      ],
    ),
  );
}

class AttendeeEventsScreen extends StatefulWidget {
  const AttendeeEventsScreen({super.key});

  @override
  State<AttendeeEventsScreen> createState() => _AttendeeEventsScreenState();
}

class _AttendeeEventsScreenState extends State<AttendeeEventsScreen> {
  final _api = EventApiService();
  final _code = TextEditingController();
  List<EventRecord> _events = [];
  bool _loading = true;
  bool _joining = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _code.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final events = await _api.listAttendeeEvents();
      if (mounted) setState(() => _events = events);
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _join() async {
    if (_code.text.trim().length < 8) {
      setState(() => _error = 'Enter the event code from your organizer.');
      return;
    }
    setState(() {
      _joining = true;
      _error = null;
    });
    try {
      final event = await _api.joinEvent(_code.text);
      if (mounted) {
        _code.clear();
        setState(
          () => _events = [
            event,
            ..._events.where((item) => item.id != event.id),
          ],
        );
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('Joined ${event.name}.')));
      }
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _joining = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('My events'),
      actions: [IconButton(onPressed: _load, icon: const Icon(Icons.refresh))],
    ),
    body: _loading
        ? const Center(child: CircularProgressIndicator())
        : ListView(
            padding: const EdgeInsets.all(20),
            children: [
              Card(
                elevation: 0,
                child: Padding(
                  padding: const EdgeInsets.all(18),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Text(
                        'Join an event',
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      const SizedBox(height: 8),
                      const Text('Enter the code shared by your organizer.'),
                      const SizedBox(height: 14),
                      TextField(
                        controller: _code,
                        textCapitalization: TextCapitalization.characters,
                        decoration: const InputDecoration(
                          labelText: 'Event code',
                        ),
                      ),
                      const SizedBox(height: 12),
                      ElevatedButton(
                        onPressed: _joining ? null : _join,
                        child: _joining
                            ? const CircularProgressIndicator()
                            : const Text('Join event'),
                      ),
                    ],
                  ),
                ),
              ),
              if (_error != null)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  child: Text(
                    _error!,
                    style: const TextStyle(color: Colors.red),
                  ),
                ),
              const SizedBox(height: 8),
              Text(
                'Joined events',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 8),
              if (_events.isEmpty)
                const Padding(
                  padding: EdgeInsets.all(28),
                  child: Text(
                    'No events yet. Join one to start finding your photos.',
                  ),
                ),
              ..._events.map(
                (event) => Card(
                  elevation: 0,
                  child: ListTile(
                    title: Text(event.name),
                    subtitle: Text(
                      event.description ?? 'Find your event photos',
                    ),
                    trailing: FilledButton(
                      onPressed: () => Navigator.of(context).push(
                        MaterialPageRoute(
                          builder: (_) => AttendeeMatchingScreen(event: event),
                        ),
                      ),
                      child: const Text('Find me'),
                    ),
                  ),
                ),
              ),
            ],
          ),
  );
}

class AttendeeMatchingScreen extends StatefulWidget {
  const AttendeeMatchingScreen({super.key, required this.event});

  final EventRecord event;

  @override
  State<AttendeeMatchingScreen> createState() => _AttendeeMatchingScreenState();
}

class _AttendeeMatchingScreenState extends State<AttendeeMatchingScreen> {
  static const _matchingTimeout = Duration(minutes: 5);

  final _api = EventApiService();
  PlatformFile? _selfie;
  bool _consented = false;
  bool _busy = false;
  String _status = 'Choose a clear selfie to search this event.';
  List<MatchResult> _results = [];
  Timer? _poller;
  DateTime? _matchingStartedAt;

  @override
  void dispose() {
    _poller?.cancel();
    super.dispose();
  }

  Future<void> _chooseSelfie() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.image,
      allowMultiple: false,
      withData: false,
    );
    if (result != null && result.files.isNotEmpty) {
      setState(() => _selfie = result.files.single);
    }
  }

  Future<void> _start() async {
    if (!_consented) {
      setState(
        () => _status = 'Please provide face-matching consent to continue.',
      );
      return;
    }
    final selfie = _selfie;
    if (selfie == null) {
      setState(() => _status = 'Choose a selfie first.');
      return;
    }
    setState(() {
      _busy = true;
      _results = [];
      _status = 'Uploading your selfie securely...';
    });
    try {
      await _api.grantFaceConsent(widget.event.id);
      final upload = await _api.requestSelfieUpload(widget.event.id);
      await _api.uploadSelfie(upload: upload, file: selfie);
      final job = await _api.createMatchingJob(
        eventId: widget.event.id,
        storageKey: upload.storageKey,
      );
      _matchingStartedAt = DateTime.now();
      _status = 'Matching in progress...';
      _poller = Timer.periodic(
        const Duration(seconds: 2),
        (_) => _poll(job.id),
      );
      await _poll(job.id);
    } catch (error) {
      if (mounted) {
        setState(() {
          _busy = false;
          _status = error.toString();
        });
      }
    }
  }

  Future<void> _poll(String jobId) async {
    try {
      final startedAt = _matchingStartedAt;
      if (startedAt != null &&
          DateTime.now().difference(startedAt) >= _matchingTimeout) {
        _poller?.cancel();
        if (mounted) {
          setState(() {
            _busy = false;
            _status =
                'Photo search is taking too long. The matching service may be offline. Please try again later.';
          });
        }
        return;
      }
      final job = await _api.getMatchingJob(jobId);
      if (!mounted) return;
      if (job.status == 'complete') {
        _poller?.cancel();
        _matchingStartedAt = null;
        final results = await _api.getMatchingResults(jobId);
        var saved = 0;
        for (final result in results) {
          try {
            final response = await http.get(Uri.parse(result.photoUrl));
            if (response.statusCode >= 200 && response.statusCode < 300) {
              await OnDeviceGalleryService().saveMatchedPhoto(
                eventId: widget.event.id,
                eventName: widget.event.name,
                photoId: result.photoId,
                bytes: response.bodyBytes,
              );
              saved++;
            }
          } catch (_) {
            // Results remain available in-app even if device saving fails.
          }
        }
        setState(() {
          _busy = false;
          _results = results;
          _status = results.isEmpty
              ? 'No matching photos were found in this event.'
              : 'Your matching photos. $saved saved to Pictures/SnapSort.';
        });
      } else if (job.status == 'failed') {
        _poller?.cancel();
        _matchingStartedAt = null;
        setState(() {
          _busy = false;
          _status =
              job.errorMessage ?? 'Matching failed. Please try another photo.';
        });
      }
    } catch (error) {
      _poller?.cancel();
      if (mounted) {
        setState(() {
          _busy = false;
          _matchingStartedAt = null;
          _status = error.toString();
        });
      }
    }
  }

  Future<void> _toggleFavorite(int index) async {
    final result = _results[index];
    try {
      final updated = await _api.setFavorite(
        photoId: result.photoId,
        favorite: !result.favorite,
      );
      if (!mounted) return;
      setState(() {
        _results[index] = MatchResult(
          photoId: result.photoId,
          similarity: result.similarity,
          photoUrl: updated.photoUrl.isEmpty
              ? result.photoUrl
              : updated.photoUrl,
          favorite: !result.favorite,
        );
      });
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(error.toString())));
      }
    }
  }

  Future<void> _download(MatchResult result) async {
    try {
      final response = await http.get(Uri.parse(result.photoUrl));
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw StateError('Download failed (${response.statusCode}).');
      }
      await OnDeviceGalleryService().saveRemoteImage(
        response.bodyBytes,
        'snapsort_${result.photoId}.jpg',
      );
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(
          const SnackBar(content: Text('Saved to Pictures/SnapSort.')),
        );
      }
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(error.toString())));
      }
    }
  }

  Future<void> _share(MatchResult result) async {
    await SharePlus.instance.share(
      ShareParams(
        text: 'My SnapSort photo: ${result.photoUrl}',
        subject: 'SnapSort photo',
      ),
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: Text(widget.event.name)),
    body: ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Text(
          'Find photos of you',
          style: Theme.of(context).textTheme.headlineSmall,
        ),
        const SizedBox(height: 8),
        Text(_status),
        const SizedBox(height: 18),
        OutlinedButton.icon(
          onPressed: _busy ? null : _chooseSelfie,
          icon: const Icon(Icons.face_retouching_natural),
          label: Text(_selfie == null ? 'Choose selfie' : _selfie!.name),
        ),
        CheckboxListTile(
          contentPadding: EdgeInsets.zero,
          value: _consented,
          onChanged: _busy
              ? null
              : (value) => setState(() => _consented = value ?? false),
          title: const Text('I consent to face matching for this event'),
          subtitle: const Text(
            'Your selfie is used only to search this event.',
          ),
        ),
        ElevatedButton(
          onPressed: _busy ? null : _start,
          child: Text(_busy ? 'Searching...' : 'Find my photos'),
        ),
        if (_busy)
          const Padding(
            padding: EdgeInsets.only(top: 18),
            child: LinearProgressIndicator(),
          ),
        if (_results.isNotEmpty) ...[
          const SizedBox(height: 24),
          GridView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            itemCount: _results.length,
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 2,
              crossAxisSpacing: 10,
              mainAxisSpacing: 10,
            ),
            itemBuilder: (_, index) {
              final result = _results[index];
              return ClipRRect(
                borderRadius: BorderRadius.circular(14),
                child: Stack(
                  fit: StackFit.expand,
                  children: [
                    Image.network(
                      result.photoUrl,
                      fit: BoxFit.cover,
                      errorBuilder: (_, error, stackTrace) => const ColoredBox(
                        color: _secondary,
                        child: Icon(Icons.broken_image_outlined),
                      ),
                    ),
                    Positioned(
                      right: 4,
                      top: 4,
                      child: PopupMenuButton<String>(
                        color: Colors.white,
                        onSelected: (action) {
                          if (action == 'favorite') _toggleFavorite(index);
                          if (action == 'download') _download(result);
                          if (action == 'share') _share(result);
                        },
                        itemBuilder: (_) => [
                          PopupMenuItem(
                            value: 'favorite',
                            child: Text(
                              result.favorite
                                  ? 'Remove favorite'
                                  : 'Add favorite',
                            ),
                          ),
                          const PopupMenuItem(
                            value: 'download',
                            child: Text('Download'),
                          ),
                          const PopupMenuItem(
                            value: 'share',
                            child: Text('Share'),
                          ),
                        ],
                        icon: const Icon(Icons.more_vert, color: Colors.white),
                      ),
                    ),
                    if (result.favorite)
                      const Positioned(
                        left: 8,
                        top: 8,
                        child: Icon(Icons.favorite, color: _highlight),
                      ),
                  ],
                ),
              );
            },
          ),
        ],
      ],
    ),
  );
}

class OrganizerEventsScreen extends StatefulWidget {
  const OrganizerEventsScreen({super.key});

  @override
  State<OrganizerEventsScreen> createState() => _OrganizerEventsScreenState();
}

class _OrganizerEventsScreenState extends State<OrganizerEventsScreen> {
  final _api = EventApiService();
  bool _loading = true;
  String? _error;
  List<EventRecord> _events = [];

  @override
  void initState() {
    super.initState();
    _loadEvents();
  }

  Future<void> _loadEvents() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final events = await _api.listEvents();
      if (mounted) setState(() => _events = events);
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Your events'),
      actions: [
        IconButton(onPressed: _loadEvents, icon: const Icon(Icons.refresh)),
      ],
    ),
    floatingActionButton: FloatingActionButton.extended(
      onPressed: () => _openEditor(),
      icon: const Icon(Icons.add),
      label: const Text('Create event'),
    ),
    body: _loading
        ? const Center(child: CircularProgressIndicator())
        : _error != null
        ? _ErrorState(message: _error!, onRetry: _loadEvents)
        : _events.isEmpty
        ? _EmptyEvents(onCreate: _openEditor)
        : RefreshIndicator(
            onRefresh: _loadEvents,
            child: ListView.builder(
              padding: const EdgeInsets.all(20),
              itemCount: _events.length,
              itemBuilder: (_, index) => _EventCard(
                event: _events[index],
                onEdit: () => _openEditor(_events[index]),
                onDelete: () => _delete(_events[index]),
                onCode: () => _showCode(_events[index]),
              ),
            ),
          ),
  );

  Future<void> _openEditor([EventRecord? event]) async {
    final result = await showModalBottomSheet<_EventDraft>(
      context: context,
      isScrollControlled: true,
      builder: (_) => _EventEditor(event: event),
    );
    if (result == null) return;
    try {
      if (event == null) {
        await _api.createEvent(
          name: result.name,
          description: result.description,
        );
      } else {
        await _api.updateEvent(
          id: event.id,
          name: result.name,
          description: result.description,
        );
      }
      await _loadEvents();
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(error.toString())));
      }
    }
  }

  Future<void> _delete(EventRecord event) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Delete event?'),
        content: Text('Delete "${event.name}"? This cannot be undone.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            style: FilledButton.styleFrom(backgroundColor: Colors.red),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      await _api.deleteEvent(event.id);
      await _loadEvents();
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(error.toString())));
      }
    }
  }

  void _showCode(EventRecord event) {
    showDialog<void>(
      context: context,
      builder: (_) => AlertDialog(
        title: Text(event.name),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            QrImageView(data: event.eventCode, size: 210),
            const SizedBox(height: 8),
            Text(
              event.eventCode,
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 6),
            const Text('Share this code or QR with attendees.'),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Done'),
          ),
        ],
      ),
    );
  }
}

class _EventCard extends StatelessWidget {
  const _EventCard({
    required this.event,
    required this.onEdit,
    required this.onDelete,
    required this.onCode,
  });

  final EventRecord event;
  final VoidCallback onEdit;
  final VoidCallback onDelete;
  final VoidCallback onCode;

  @override
  Widget build(BuildContext context) => Card(
    elevation: 0,
    margin: const EdgeInsets.only(bottom: 12),
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  event.name,
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ),
              PopupMenuButton<String>(
                onSelected: (value) {
                  if (value == 'edit') onEdit();
                  if (value == 'delete') onDelete();
                },
                itemBuilder: (_) => const [
                  PopupMenuItem(value: 'edit', child: Text('Edit')),
                  PopupMenuItem(value: 'delete', child: Text('Delete')),
                ],
              ),
            ],
          ),
          if (event.description?.isNotEmpty == true)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Text(
                event.description!,
                style: const TextStyle(color: Colors.black54),
              ),
            ),
          const SizedBox(height: 14),
          OutlinedButton.icon(
            onPressed: onCode,
            icon: const Icon(Icons.qr_code_2),
            label: Text('Event code  ${event.eventCode}'),
          ),
        ],
      ),
    ),
  );
}

class _EventEditor extends StatefulWidget {
  const _EventEditor({this.event});
  final EventRecord? event;

  @override
  State<_EventEditor> createState() => _EventEditorState();
}

class _EventEditorState extends State<_EventEditor> {
  late final TextEditingController _name;
  late final TextEditingController _description;
  final _formKey = GlobalKey<FormState>();

  @override
  void initState() {
    super.initState();
    _name = TextEditingController(text: widget.event?.name);
    _description = TextEditingController(text: widget.event?.description);
  }

  @override
  void dispose() {
    _name.dispose();
    _description.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Padding(
    padding: EdgeInsets.fromLTRB(
      24,
      24,
      24,
      MediaQuery.viewInsetsOf(context).bottom + 24,
    ),
    child: Form(
      key: _formKey,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            widget.event == null ? 'Create event' : 'Edit event',
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const SizedBox(height: 18),
          TextFormField(
            controller: _name,
            decoration: const InputDecoration(labelText: 'Event name'),
            validator: (value) => value == null || value.trim().isEmpty
                ? 'Enter an event name'
                : null,
          ),
          const SizedBox(height: 14),
          TextFormField(
            controller: _description,
            maxLines: 3,
            decoration: const InputDecoration(
              labelText: 'Description (optional)',
            ),
          ),
          const SizedBox(height: 18),
          ElevatedButton(
            onPressed: () {
              if (_formKey.currentState!.validate()) {
                Navigator.pop(
                  context,
                  _EventDraft(
                    name: _name.text.trim(),
                    description: _description.text.trim().isEmpty
                        ? null
                        : _description.text.trim(),
                  ),
                );
              }
            },
            child: Text(widget.event == null ? 'Create event' : 'Save changes'),
          ),
        ],
      ),
    ),
  );
}

class _EventDraft {
  const _EventDraft({required this.name, required this.description});
  final String name;
  final String? description;
}

class _EmptyEvents extends StatelessWidget {
  const _EmptyEvents({required this.onCreate});
  final VoidCallback onCreate;

  @override
  Widget build(BuildContext context) => Center(
    child: Padding(
      padding: const EdgeInsets.all(32),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.event_note_outlined, size: 56, color: _primary),
          const SizedBox(height: 14),
          Text('No events yet', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 8),
          const Text(
            'Create an event to generate a code and invite attendees.',
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 18),
          ElevatedButton(
            onPressed: onCreate,
            child: const Text('Create your first event'),
          ),
        ],
      ),
    ),
  );
}

class _ErrorState extends StatelessWidget {
  const _ErrorState({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) => Center(
    child: Padding(
      padding: const EdgeInsets.all(28),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(
            Icons.cloud_off_outlined,
            size: 48,
            color: Colors.redAccent,
          ),
          const SizedBox(height: 12),
          Text(message, textAlign: TextAlign.center),
          const SizedBox(height: 16),
          OutlinedButton(onPressed: onRetry, child: const Text('Try again')),
        ],
      ),
    ),
  );
}

class PhotographerEventsScreen extends StatefulWidget {
  const PhotographerEventsScreen({super.key});

  @override
  State<PhotographerEventsScreen> createState() =>
      _PhotographerEventsScreenState();
}

class _PhotographerEventsScreenState extends State<PhotographerEventsScreen> {
  final _eventsApi = EventApiService();
  bool _loading = true;
  String? _error;
  List<EventRecord> _events = [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final response = await _eventsApi.listPhotographerEvents();
      if (mounted) setState(() => _events = response);
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Photographer events'),
      actions: [
        IconButton(onPressed: _joinByCode, icon: const Icon(Icons.add_link)),
        IconButton(onPressed: _load, icon: const Icon(Icons.refresh)),
      ],
    ),
    body: _loading
        ? const Center(child: CircularProgressIndicator())
        : _error != null
        ? _ErrorState(message: _error!, onRetry: _load)
        : _events.isEmpty
        ? const Center(
            child: Padding(
              padding: EdgeInsets.all(32),
              child: Text(
                'Join an event with its code to start uploading photos.',
                textAlign: TextAlign.center,
              ),
            ),
          )
        : ListView(
            padding: const EdgeInsets.all(20),
            children: _events
                .map(
                  (event) => Card(
                    elevation: 0,
                    child: ListTile(
                      title: Text(event.name),
                      subtitle: Text(event.description ?? 'Ready for uploads'),
                      trailing: FilledButton(
                        onPressed: () => Navigator.of(context).push(
                          MaterialPageRoute(
                            builder: (_) => PhotoUploadScreen(event: event),
                          ),
                        ),
                        child: const Text('Upload'),
                      ),
                    ),
                  ),
                )
                .toList(),
          ),
  );

  Future<void> _joinByCode() async {
    final controller = TextEditingController();
    final code = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Join event'),
        content: TextField(
          controller: controller,
          textCapitalization: TextCapitalization.characters,
          decoration: const InputDecoration(labelText: 'Event code'),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, controller.text),
            child: const Text('Join'),
          ),
        ],
      ),
    );
    controller.dispose();
    if (code == null || code.trim().isEmpty || !mounted) return;
    try {
      await _eventsApi.joinPhotographerEvent(code);
      await _load();
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(error.toString())));
      }
    }
  }
}

class PhotoUploadScreen extends StatefulWidget {
  const PhotoUploadScreen({super.key, required this.event});

  final EventRecord event;

  @override
  State<PhotoUploadScreen> createState() => _PhotoUploadScreenState();
}

class _PhotoUploadScreenState extends State<PhotoUploadScreen> {
  final _service = PhotoUploadService();
  final List<UploadItem> _items = [];
  bool _working = false;

  Future<void> _select() async {
    final result = await FilePicker.platform.pickFiles(
      allowMultiple: true,
      type: FileType.custom,
      allowedExtensions: ['jpg', 'jpeg', 'png', 'webp'],
      withData: false,
    );
    if (result == null || result.files.isEmpty) return;
    setState(() {
      _items
        ..clear()
        ..addAll(result.files.map(UploadItem.new));
    });
  }

  Future<void> _uploadAll() async {
    if (_items.isEmpty) return;
    setState(() => _working = true);
    var uploaded = 0;
    var failed = 0;
    for (final item in _items) {
      if (item.status == UploadStatus.complete) continue;
      setState(() {
        item.status = UploadStatus.uploading;
        item.error = null;
      });
      try {
        await _service.upload(
          eventId: widget.event.id,
          item: item,
          onProgress: (progress) {
            if (mounted) setState(() => item.progress = progress);
          },
        );
        uploaded++;
        if (mounted) setState(() => item.status = UploadStatus.complete);
      } catch (error) {
        failed++;
        if (mounted) {
          setState(() {
            item.status = UploadStatus.failed;
            item.error = error.toString();
          });
        }
      }
    }
    if (mounted) {
      setState(() => _working = false);
      final message = failed == 0
          ? '$uploaded photo${uploaded == 1 ? '' : 's'} uploaded successfully.'
          : '$uploaded uploaded, $failed failed. Tap upload to retry failed items.';
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(message)));
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: Text(widget.event.name)),
    body: ListView(
      padding: const EdgeInsets.all(20),
      children: [
        OutlinedButton.icon(
          onPressed: _working ? null : _select,
          icon: const Icon(Icons.photo_library_outlined),
          label: const Text('Select photos'),
        ),
        const SizedBox(height: 12),
        if (_items.isEmpty)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 50),
            child: Text(
              'Select multiple JPG, PNG, or WebP images to begin.',
              textAlign: TextAlign.center,
            ),
          ),
        ..._items.map(
          (item) => Card(
            elevation: 0,
            child: ListTile(
              leading: const Icon(Icons.image_outlined, color: _primary),
              title: Text(item.file.name),
              subtitle: item.status == UploadStatus.uploading
                  ? LinearProgressIndicator(value: item.progress)
                  : Text(
                      item.error ??
                          switch (item.status) {
                            UploadStatus.queued => 'Queued',
                            UploadStatus.complete => 'Uploaded',
                            UploadStatus.failed =>
                              'Upload failed; retry available',
                            UploadStatus.uploading => 'Uploading',
                          },
                    ),
              trailing: item.status == UploadStatus.complete
                  ? const Icon(Icons.check_circle, color: _accent)
                  : null,
            ),
          ),
        ),
        const SizedBox(height: 18),
        ElevatedButton(
          onPressed: _working || _items.isEmpty ? null : _uploadAll,
          child: Text(_working ? 'Uploading...' : 'Upload selected photos'),
        ),
      ],
    ),
  );
}
