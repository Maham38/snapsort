import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';

enum UserRole { organizer, photographer, attendee }

class AuthService {
  AuthService._();

  static final instance = AuthService._();

  FirebaseAuth get _auth => FirebaseAuth.instance;
  FirebaseFirestore get _firestore => FirebaseFirestore.instance;

  Stream<User?> get authStateChanges => _auth.authStateChanges();
  User? get currentUser => _auth.currentUser;

  Future<UserCredential> signIn({
    required String email,
    required String password,
  }) {
    return _auth.signInWithEmailAndPassword(
      email: email.trim(),
      password: password,
    );
  }

  Future<UserCredential> createAccount({
    required String name,
    required String email,
    required String password,
  }) async {
    final credential = await _auth.createUserWithEmailAndPassword(
      email: email.trim(),
      password: password,
    );
    await credential.user?.updateDisplayName(name.trim());
    await _saveProfile(credential.user!, name: name);
    return credential;
  }

  Future<void> saveRole(UserRole role) async {
    final user = currentUser;
    if (user == null) {
      throw StateError('You must be signed in to select a role.');
    }
    await _saveProfile(user, role: role);
  }

  Future<void> sendPasswordReset(String email) {
    return _auth.sendPasswordResetEmail(email: email.trim());
  }

  Future<void> signOut() => _auth.signOut();

  Future<void> _saveProfile(User user, {String? name, UserRole? role}) {
    return _firestore.collection('users').doc(user.uid).set({
      if (name != null) 'displayName': name.trim(),
      if (role != null) 'role': role.name,
      'email': user.email,
      'updatedAt': FieldValue.serverTimestamp(),
      if (name != null) 'createdAt': FieldValue.serverTimestamp(),
    }, SetOptions(merge: true));
  }
}

String authErrorMessage(Object error) {
  if (error is FirebaseAuthException) {
    return switch (error.code) {
      'invalid-credential' ||
      'user-not-found' ||
      'wrong-password' => 'That email or password is not correct.',
      'email-already-in-use' => 'An account already exists for that email.',
      'weak-password' => 'Choose a stronger password.',
      'network-request-failed' =>
        'Network unavailable. Check your connection and try again.',
      'too-many-requests' =>
        'Too many attempts. Please wait a moment and try again.',
      _ => error.message ?? 'Authentication failed. Please try again.',
    };
  }
  if (error is FirebaseException && error.code == 'permission-denied') {
    return 'Your account does not have permission for this action.';
  }
  if (error is StateError) {
    return error.message;
  }
  return 'Something went wrong. Please try again.';
}
