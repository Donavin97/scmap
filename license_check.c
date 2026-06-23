/* license_check.c — verify scmap license certificates via OpenSSL.
 *
 * Compiled once, shipped to paying customers as license_check.so.
 * Community edition uses a Python stub instead.
 *
 * Build:
 *   gcc -shared -fPIC -o license_check.so license_check.c -lcrypto
 *
 * Embedded CA certificate — public key material (not secret).
 * The corresponding private key (scmap-ca-key.pem) is kept offline
 * and used only by the developer to sign customer certificates.
 */

#include <openssl/pem.h>
#include <openssl/x509.h>
#include <openssl/x509v3.h>
#include <openssl/err.h>
#include <openssl/asn1.h>
#include <string.h>
#include <time.h>
#include <stdarg.h>

/* ── Embedded CA certificate ────────────────────────────────────────────── */
static const char CA_CERT_PEM[] =
    "-----BEGIN CERTIFICATE-----\n"
    "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\n"
    "lreBz//nR3mopibEgcPKNbk=\n"
    "-----END CERTIFICATE-----\n";

/* ── Error / customer name buffers (thread-unsafe, fine for CLI use) ──── */
static char last_error[512];
static char last_customer[256];

static void set_error(const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(last_error, sizeof(last_error), fmt, ap);
    va_end(ap);
}

static int load_ca_cert(X509 **out) {
    BIO *bio = BIO_new_mem_buf(CA_CERT_PEM, -1);
    if (!bio) { set_error("BIO_new_mem_buf failed"); return -1; }
    *out = PEM_read_bio_X509(bio, NULL, NULL, NULL);
    BIO_free(bio);
    if (!*out) { set_error("failed to parse embedded CA cert"); return -1; }
    return 0;
}

static int verify_cert_against_ca(X509 *cert, X509 *ca_cert) {
    EVP_PKEY *ca_pubkey = X509_get_pubkey(ca_cert);
    if (!ca_pubkey) { set_error("failed to extract CA public key"); return -1; }

    int rc = X509_verify(cert, ca_pubkey);
    EVP_PKEY_free(ca_pubkey);

    if (rc != 1) {
        set_error("certificate signature invalid");
        return -1;
    }
    return 0;
}

static int check_validity(X509 *cert) {
    time_t now = time(NULL);
    if (now == (time_t)-1) { set_error("time() failed"); return -1; }

    if (X509_cmp_time(X509_get0_notBefore(cert), &now) > 0) {
        set_error("certificate not yet valid");
        return -1;
    }
    if (X509_cmp_time(X509_get0_notAfter(cert), &now) < 0) {
        set_error("certificate has expired");
        return -1;
    }
    return 0;
}

static int extract_customer(X509 *cert) {
    X509_NAME *subj = X509_get_subject_name(cert);
    if (!subj) { set_error("no subject"); return -1; }

    char buf[256];
    int len = X509_NAME_get_text_by_NID(subj, NID_commonName, buf, sizeof(buf));
    if (len < 0 || len >= (int)sizeof(buf)) {
        set_error("no common name (CN) in cert");
        return -1;
    }
    buf[len] = '\0';
    snprintf(last_customer, sizeof(last_customer), "%s", buf);
    /* strip trailing whitespace (X509_NAME_get_text_by_NID may pad) */
    for (int i = (int)strlen(last_customer) - 1; i >= 0 && last_customer[i] == ' '; i--)
        last_customer[i] = '\0';
    return 0;
}


/* ═══════════════════════════════════════════════════════════════════════════
 * Public API — called from _license_pro.py via ctypes
 * ═══════════════════════════════════════════════════════════════════════════ */

/* Returns:
 *    0  — valid license
 *   -1  — cert file not found
 *   -2  — parse / signature / expiry error (see get_error())
 */
int verify_license(const char *cert_path) {
    last_error[0] = '\0';
    last_customer[0] = '\0';

    /* Load CA cert */
    X509 *ca_cert = NULL;
    if (load_ca_cert(&ca_cert) != 0) return -2;

    /* Load customer cert from file */
    BIO *bio = BIO_new_file(cert_path, "r");
    if (!bio) {
        X509_free(ca_cert);
        set_error("cannot open certificate file: %s", cert_path);
        return -1;
    }
    X509 *cert = PEM_read_bio_X509(bio, NULL, NULL, NULL);
    BIO_free(bio);
    if (!cert) {
        X509_free(ca_cert);
        set_error("failed to parse certificate file");
        return -2;
    }

    /* Verify signature */
    if (verify_cert_against_ca(cert, ca_cert) != 0) {
        X509_free(cert); X509_free(ca_cert);
        return -2;
    }

    /* Check validity dates */
    if (check_validity(cert) != 0) {
        X509_free(cert); X509_free(ca_cert);
        return -2;
    }

    /* Extract customer name */
    extract_customer(cert);

    X509_free(cert);
    X509_free(ca_cert);
    return 0;
}

const char *get_error(void) {
    return last_error[0] ? last_error : "unknown error";
}

const char *get_customer(void) {
    return last_customer[0] ? last_customer : NULL;
}
