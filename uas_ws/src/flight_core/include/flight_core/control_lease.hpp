#pragma once

#include <cstdint>
#include <optional>
#include <string>

namespace flight_core
{

/// Tracks which client has exclusive control. Leases never expire; they end
/// only by release or reset.
class ControlLease
{
public:
  /// Grant the lease to `client_name`, or return nullopt if it is already held.
  std::optional<uint32_t> acquire(const std::string & client_name);

  /// End the lease if `lease_id` holds it.
  bool release(uint32_t lease_id);

  /// End any lease regardless of holder.
  void reset();

  bool is_holder(uint32_t lease_id) const;
  bool held() const;
  const std::string & holder_name() const;

private:
  std::optional<uint32_t> lease_id_;
  std::string holder_name_;
  uint32_t next_id_{1};
};

}  // namespace flight_core
