#include "flight_core/control_lease.hpp"

namespace flight_core
{

std::optional<uint32_t> ControlLease::acquire(const std::string & client_name)
{
  if (lease_id_) {
    return std::nullopt;
  }
  // Skip 0 so a default-initialised request field never matches.
  if (next_id_ == 0) {
    next_id_ = 1;
  }
  lease_id_ = next_id_++;
  holder_name_ = client_name;
  return lease_id_;
}

bool ControlLease::release(uint32_t lease_id)
{
  if (!is_holder(lease_id)) {
    return false;
  }
  reset();
  return true;
}

void ControlLease::reset()
{
  lease_id_.reset();
  holder_name_.clear();
}

bool ControlLease::is_holder(uint32_t lease_id) const
{
  return lease_id_ && *lease_id_ == lease_id;
}

bool ControlLease::held() const
{
  return lease_id_.has_value();
}

const std::string & ControlLease::holder_name() const
{
  return holder_name_;
}

}  // namespace flight_core
