Name:           pydep
Version:        0.1.0
Release:        1%{?dist}
Summary:        Multi-language dependency manager TUI
License:        MIT
URL:            https://github.com/EslamMohamed365/pydep
BuildArch:      x86_64

%description
A fully keyboard-driven terminal UI for managing
Python, JavaScript, and Go dependencies.

%install
mkdir -p %{buildroot}/usr/bin
install -m 755 %{_sourcedir}/pydep %{buildroot}/usr/bin/pydep

%files
/usr/bin/pydep

%changelog
* Mon Feb 23 2026 Eslam Mohamed <eslam@example.com> - 0.1.0-1
- Initial package
